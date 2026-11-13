"""工具层测试：白名单、参数校验、高危确认、用户隔离。

**为什么这个文件是全项目最该有测试的地方**：
`tools.py` 是模型唯一能"动手"的入口。模型输出的是文本，
只有经过工具层才会变成 SQL、变成删除、变成对外请求。
这里出错不是"体验不好"，是数据被删、越权被读。

四组测试对应四道闸：
  1. safe_eval —— 算术表达式不能变成代码执行
  2. 参数转换   —— 模型给的奇怪类型不能变成异常
  3. execute    —— 白名单 + 高危确认 + 永不抛异常
  4. 业务链路   —— 正常读写 + 跨用户隔离
"""

import json

import pytest

from agent_lab.app.services import tools

# ============================================================
# 一、calculator 的安全求值
# ============================================================


class TestSafeEvalAccepts:
    """合法表达式必须算对（算错比拒绝更危险 —— 没人会去核对）。"""

    def test_basic_arithmetic(self) -> None:
        assert tools.safe_eval("1+2") == 3.0
        assert tools.safe_eval("(12*35+8)/2") == 214.0

    def test_all_supported_operators(self) -> None:
        assert tools.safe_eval("7//2") == 3.0
        assert tools.safe_eval("7%3") == 1.0
        assert tools.safe_eval("2**10") == 1024.0

    def test_unary_and_negative(self) -> None:
        assert tools.safe_eval("-5+3") == -2.0
        assert tools.safe_eval("+7") == 7.0
        assert tools.safe_eval("-(3*4)") == -12.0


class TestSafeEvalRejects:
    """结构性拒绝：不认识的语法树节点一律不执行。"""

    @pytest.mark.parametrize(
        "expr",
        [
            "__import__('os').system('echo pwned')",  # 代码执行
            "().__class__.__bases__",  # 属性穿透
            "x + 1",  # 名字引用
            "[1, 2, 3]",  # 列表
            "'abc'",  # 字符串常量
            "True + 1",  # bool 会被当成 1
            "abs(-1)",  # 函数调用
            "1 if 1 else 2",  # 条件表达式
        ],
    )
    def test_rejects_non_arithmetic(self, expr: str) -> None:
        with pytest.raises(ValueError):
            tools.safe_eval(expr)

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="表达式为空"):
            tools.safe_eval("   ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError, match="表达式太长"):
            tools.safe_eval("1+" * 150 + "1")

    def test_zero_division_has_friendly_message(self) -> None:
        # 除零是用户输入问题，不该冒出一句 ZeroDivisionError 给模型看
        with pytest.raises(ValueError, match="除数不能为 0"):
            tools.safe_eval("1/0")

    def test_power_bomb_is_blocked(self) -> None:
        # 9**9**9 右结合 = 9**(9**9)，不拦会算到天荒地老
        with pytest.raises(ValueError, match="指数不能超过"):
            tools.safe_eval("9**9**9")

    def test_huge_result_is_blocked(self) -> None:
        with pytest.raises(ValueError, match="结果太大"):
            tools.safe_eval("10**100")

    def test_syntax_error_is_value_error(self) -> None:
        with pytest.raises(ValueError, match="语法错误"):
            tools.safe_eval("1 +")


# ============================================================
# 二、参数宽容转换
# ============================================================


class TestCoercion:
    """模型给的参数类型经常不对，转换必须宽容且**不抛异常**。"""

    def test_bool_is_not_int(self) -> None:
        # True 是 int 的子类，不排除的话 True 会变成 id=1
        assert tools._as_int(True) is None
        assert tools._as_int(False) is None

    def test_int_passthrough(self) -> None:
        assert tools._as_int(7) == 7
        assert tools._as_int(0) == 0

    def test_string_number_tolerated(self) -> None:
        assert tools._as_int("3") == 3
        assert tools._as_int(" -3 ") == -3

    @pytest.mark.parametrize("raw", ["3.5", "abc", "--3", "", "0x10", "1e3"])
    def test_invalid_returns_none_instead_of_raising(self, raw: str) -> None:
        # 回归测试：这里曾经用 isdigit 预筛，"--3" 能过筛但 int() 会炸，
        # 「参数不合法」被误报成「工具执行失败」。
        assert tools._as_int(raw) is None

    def test_non_string_non_int(self) -> None:
        assert tools._as_int(None) is None
        assert tools._as_int([1]) is None
        assert tools._as_int(1.5) is None

    def test_bool_coercion(self) -> None:
        assert tools._as_bool(True) is True
        assert tools._as_bool("true") is None  # 不做字符串推断了，只认真 bool
        assert tools._as_str(1) is None
        assert tools._as_str("x") == "x"


# ============================================================
# 三、execute 入口：白名单 / 高危确认 / 永不抛异常
# ============================================================


class TestExecuteGuards:
    async def test_unknown_tool_rejected_by_whitelist(self, db) -> None:
        out = json.loads(await tools.execute(db, "rm_rf", "{}", user_id="u1"))
        assert out["code"] == "TOOL_NOT_ALLOWED"
        assert out["guard"] is True

    async def test_malformed_json_returns_error(self, db) -> None:
        out = json.loads(await tools.execute(db, "list_todos", "{not json", user_id="u1"))
        assert "不是合法 JSON" in out["error"]

    @pytest.mark.parametrize("raw", ["[1,2]", '"text"', "null", "42"])
    async def test_non_object_json_returns_error(self, db, raw: str) -> None:
        out = json.loads(await tools.execute(db, "list_todos", raw, user_id="u1"))
        assert out["error"] == "参数必须是 JSON 对象"

    async def test_empty_arguments_treated_as_empty_object(self, db) -> None:
        # 有些模型对无参工具只回空串
        out = json.loads(await tools.execute(db, "list_todos", "", user_id="u1"))
        assert out["count"] == 0

    async def test_delete_without_user_intent_is_blocked(self, db) -> None:
        # 参数完全合法，但用户没说要删 —— 这才是真正要防的场景
        await tools.execute(db, "create_todo", '{"title":"买菜"}', user_id="u1")
        out = json.loads(
            await tools.execute(
                db,
                "delete_todo",
                '{"id":1}',
                user_text="看看我有哪些待办",
                user_id="u1",
            )
        )
        assert out["code"] == "TOOL_NEEDS_CONFIRMATION"
        assert out["guard"] is True

    async def test_batch_delete_is_blocked(self, db) -> None:
        out = json.loads(
            await tools.execute(
                db,
                "delete_todo",
                '{"id":1}',
                user_text="删掉所有待办",
                user_id="u1",
            )
        )
        assert out["code"] == "TOOL_BATCH_FORBIDDEN"

    async def test_execute_never_raises(self, db) -> None:
        """文档承诺「永远返回字符串、永不抛异常」，这里逐条验证。

        崩一次就等于整轮对话中断，而且模型拿不到失败原因、无法自我纠正。
        """
        for raw in ["{", "[]", "null", '"x"', "{}"]:
            out = await tools.execute(db, "list_todos", raw, user_id="u1")
            assert isinstance(out, str)
            json.loads(out)  # 必须是合法 JSON，否则前端/模型都解析不了


# ============================================================
# 四、业务链路 + 用户隔离
# ============================================================


class TestTodoTools:
    async def test_create_then_list(self, db) -> None:
        created = json.loads(
            await tools.execute(db, "create_todo", '{"title":"买菜"}', user_id="u1")
        )
        assert created["ok"] is True
        assert created["todo"]["title"] == "买菜"
        assert created["todo"]["done"] is False

        listed = json.loads(await tools.execute(db, "list_todos", "{}", user_id="u1"))
        assert listed["count"] == 1

    async def test_empty_list_has_friendly_note(self, db) -> None:
        out = json.loads(await tools.execute(db, "list_todos", "{}", user_id="u1"))
        assert out["count"] == 0
        # 只回一个空数组，模型容易理解成"调用失败"，所以要带一句说明
        assert "note" in out

    async def test_create_without_title_is_rejected(self, db) -> None:
        out = json.loads(await tools.execute(db, "create_todo", '{"title":"   "}', user_id="u1"))
        assert out["error"] == "title 不能为空"

    async def test_title_too_long_reported_as_text(self, db) -> None:
        # Pydantic 的 ValidationError 必须被转成文本，不能冒到上层
        payload = json.dumps({"title": "长" * 201})
        out = json.loads(await tools.execute(db, "create_todo", payload, user_id="u1"))
        assert "参数校验失败" in out["error"]

    async def test_update_only_done(self, db) -> None:
        await tools.execute(db, "create_todo", '{"title":"写周报"}', user_id="u1")
        out = json.loads(
            await tools.execute(db, "update_todo", '{"id":1,"done":true}', user_id="u1")
        )
        assert out["ok"] is True
        assert out["todo"]["done"] is True
        assert out["todo"]["title"] == "写周报"  # 没传的字段不能被清空

    async def test_update_requires_at_least_one_field(self, db) -> None:
        await tools.execute(db, "create_todo", '{"title":"写周报"}', user_id="u1")
        out = json.loads(await tools.execute(db, "update_todo", '{"id":1}', user_id="u1"))
        assert out["error"] == "title 和 done 至少要改一个"

    async def test_update_missing_id(self, db) -> None:
        out = json.loads(await tools.execute(db, "update_todo", '{"done":true}', user_id="u1"))
        assert out["error"] == "缺少有效的 id"

    async def test_delete_nonexistent_id(self, db) -> None:
        out = json.loads(
            await tools.execute(
                db,
                "delete_todo",
                '{"id":999}',
                user_text="删掉 999 这条",
                user_id="u1",
            )
        )
        assert out["code"] == "TODO_NOT_FOUND"

    async def test_full_cycle(self, db) -> None:
        await tools.execute(db, "create_todo", '{"title":"临时任务"}', user_id="u1")
        deleted = json.loads(
            await tools.execute(
                db,
                "delete_todo",
                '{"id":1}',
                user_text="把「临时任务」删掉",
                user_id="u1",
            )
        )
        assert deleted["ok"] is True
        listed = json.loads(await tools.execute(db, "list_todos", "{}", user_id="u1"))
        assert listed["count"] == 0


class TestUserIsolation:
    """多租户最危险的路径：模型不知道"用户是谁"，它只看到参数。

    所以 user_id 只能由 agent 从会话归属传下来，
    一旦透传到工具的参数里，一句提示注入就能操作别人的数据。
    """

    async def test_other_user_cannot_see_todos(self, db) -> None:
        await tools.execute(db, "create_todo", '{"title":"alice 的私事"}', user_id="alice")

        bob_list = json.loads(await tools.execute(db, "list_todos", "{}", user_id="bob"))
        assert bob_list["count"] == 0

        alice_list = json.loads(await tools.execute(db, "list_todos", "{}", user_id="alice"))
        assert alice_list["count"] == 1

    async def test_other_user_cannot_delete(self, db) -> None:
        await tools.execute(db, "create_todo", '{"title":"alice 的私事"}', user_id="alice")

        # bob 明确说了"删掉"，过了意图检查，但 id 属于 alice
        out = json.loads(
            await tools.execute(
                db,
                "delete_todo",
                '{"id":1}',
                user_text="删掉这条",
                user_id="bob",
            )
        )
        assert out["code"] == "TODO_NOT_FOUND"

        alice_list = json.loads(await tools.execute(db, "list_todos", "{}", user_id="alice"))
        assert alice_list["count"] == 1, "别人的删除请求不能真的删掉数据"

    async def test_other_user_cannot_update(self, db) -> None:
        await tools.execute(db, "create_todo", '{"title":"alice 的私事"}', user_id="alice")
        out = json.loads(
            await tools.execute(db, "update_todo", '{"id":1,"done":true}', user_id="bob")
        )
        assert out["code"] == "TODO_NOT_FOUND"


class TestCalculatorTool:
    async def test_whole_number_stays_int(self, db) -> None:
        # 70.0 会被模型复述成"70.0 个"，难看且显得不专业
        out = json.loads(
            await tools.execute(db, "calculator", '{"expression":"(12*35+8)/2"}', user_id="u1")
        )
        assert out["result"] == 214
        assert isinstance(out["result"], int)

    async def test_fraction_keeps_decimals(self, db) -> None:
        out = json.loads(
            await tools.execute(db, "calculator", '{"expression":"1/3"}', user_id="u1")
        )
        assert out["result"] == pytest.approx(0.3333, abs=1e-3)

    async def test_invalid_expression_returns_error_text(self, db) -> None:
        out = json.loads(
            await tools.execute(db, "calculator", '{"expression":"1/0"}', user_id="u1")
        )
        assert "除数不能为 0" in out["error"]
        assert "result" not in out
