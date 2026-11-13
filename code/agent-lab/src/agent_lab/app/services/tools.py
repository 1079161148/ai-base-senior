"""Agent 可调用的工具集合。

**为什么直接调 service 层，而不是走一遍自己的 HTTP 接口**：
同一进程内没必要为了"复用"绕一圈网络 —— 那只会多出序列化开销、多一个失败点，
还得处理自己调自己的鉴权。`api/v1/todos.py` 的注释里早就写明了这层设计意图：
「任何业务判断都不写在这里，否则将来接 Agent 工具时逻辑要抄第二遍」。
现在就是"将来"。

**为什么参数要写 JSON Schema**：
模型是**读着这段 schema** 决定"要不要调、传什么参数"的。
description 本质上是写给模型看的提示词，写得含糊，模型就会乱调或者干脆不调。
例如 list_todos 的说明里明确要求"不要凭记忆回答"，就是为了压住幻觉。

**为什么工具出错也返回字符串而不是抛异常**：
模型需要看到「失败了，原因是 X」，才能自己纠正（比如换个 id 重试，或向用户解释）。
直接把异常抛给上层，用户只会看到一句"生成失败"，问题也丢了。
"""

import ast
import json
import logging
import operator
from typing import cast

import aiosqlite
from pydantic import ValidationError

from ..core.errors import ApiError
from ..models.todo import TodoCreate, TodoUpdate
from . import guard
from . import todo as todo_service

logger = logging.getLogger(__name__)

# 工具声明。形状照抄 OpenAI 的 function calling 协议，
# 换任何兼容厂商都不用改。
TOOLS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "list_todos",
            "description": (
                "列出全部待办事项，返回每条待办的 id、标题和完成状态。"
                "用户问到「我有哪些待办」「有完成的吗」「一共有几条」这类问题时，"
                "**必须先调用它**，绝不能凭上下文猜测——你看不到数据库。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_todo",
            "description": "新增一条待办事项。用户说「记一下」「加一条」「提醒我」时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "待办内容，简洁明确，不超过 200 字",
                    }
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_todo",
            "description": (
                "修改一条待办：改标题，或标记完成/未完成。"
                "执行前必须先知道 id，若用户没给 id 就先用 list_todos 查出来，不要猜。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "待办 id"},
                    "title": {
                        "type": "string",
                        "description": "新标题；不改标题就不要传",
                    },
                    "done": {
                        "type": "boolean",
                        "description": "true 标记完成，false 标记未完成；不改状态就不要传",
                    },
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_todo",
            "description": "删除一条待办。只在用户**明确要求删除**时调用，拿不准就先问。",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "待办 id"},
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": (
                "在已上传的文档中检索相关内容。涉及文档里的知识点或技术规范时"
                "**必须先调这个**——你看不到文档内容，任何凭上下文推测的答案都是编造的。"
                "用自然语言描述你想查什么即可，不需要写检索语法。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索关键词或自然语言查询，如'分块大小的建议'、'RRF 是什么'",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "精确计算数学表达式，支持 + - * / // % ** 和括号。"
                "涉及数字计算时用它，**不要心算**——大模型算三位数乘法经常出错。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "例如 (12*35+8)/2",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]

# ---- calculator 的安全求值 ----
#
# **绝对不能用 eval**：那等于把代码执行权交给模型（进而交给任何能构造输入的人）。
# `__import__('os').system('rm -rf /')` 就是一个合法的"表达式"。
#
# ast 白名单的思路：先把字符串解析成语法树，只允许"数字 + 四则运算 + 括号"
# 这几种节点，遇到函数调用、属性访问、名字引用一律拒绝。
# 结构上做不到的事，比事后过滤黑名单可靠。

_BINOPS: dict[type[ast.operator], object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARYOPS: dict[type[ast.unaryop], object] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_EXPR_MAX_LEN = 200
# 指数上限。不限制的话 `9**9**9` 会让 CPU 算到天荒地老 ——
# 这属于"表达式炸弹"，和 ReDoS 是同一类问题。
_POW_MAX_EXP = 100
_RESULT_MAX = 1e15


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        value = node.value
        # bool 是 int 的子类，True 会被当成 1，这里显式排除
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("只支持数字常量")
        return float(value)

    if isinstance(node, ast.BinOp):
        func = _BINOPS.get(type(node.op))
        if func is None:
            raise ValueError(f"不支持的运算符：{type(node.op).__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _POW_MAX_EXP:
            raise ValueError(f"指数不能超过 {_POW_MAX_EXP}")
        return float(cast("object", func)(left, right))  # type: ignore[operator]

    if isinstance(node, ast.UnaryOp):
        unary = _UNARYOPS.get(type(node.op))
        if unary is None:
            raise ValueError("不支持的一元运算符")
        return float(cast("object", unary)(_eval_node(node.operand)))  # type: ignore[operator]

    raise ValueError("表达式里只能有数字、括号和 + - * / // % **")


def safe_eval(expression: str) -> float:
    """安全地计算算术表达式。非法输入抛 ValueError。"""
    text = expression.strip()
    if not text:
        raise ValueError("表达式为空")
    if len(text) > _EXPR_MAX_LEN:
        raise ValueError(f"表达式太长（上限 {_EXPR_MAX_LEN} 字符）")

    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"表达式语法错误：{exc.msg}") from exc

    try:
        result = _eval_node(tree.body)
    except ZeroDivisionError:
        # 除零是**用户输入问题**，不是程序 bug。
        # 不在这里转换的话，它会掉进 execute() 的兜底分支，
        # 既打出一段吓人的 traceback，又给模型一句没用的"ZeroDivisionError"。
        raise ValueError("除数不能为 0") from None
    except OverflowError:
        raise ValueError("数值溢出") from None

    if abs(result) > _RESULT_MAX:
        raise ValueError("结果太大")
    return result


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_int(value: object) -> int | None:
    # bool 是 int 的子类，必须排除，否则 True 会被当成 id=1
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    # 有些模型会返回 "3" 这种字符串形式的数字，宽容处理。
    #
    # **不要用 isdigit() 预筛**：`"--3".lstrip("-")` 结果是 "3"，
    # isdigit 通过，但 int("--3") 会抛 ValueError ——
    # 于是「参数不合法」被误报成「工具执行失败」，用户看到的是程序故障。
    # 直接 try int()，语义和边界都由标准库保证。
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _as_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


async def _run(
    db: aiosqlite.Connection,
    name: str,
    args: dict[str, object],
    user_id: str,
) -> object:
    """执行具体工具，返回可 JSON 序列化的结果。

    `user_id` 由 agent 从会话归属传下来，**工具自己不做鉴权**：
    它只保证每条 SQL / 每次检索都带上这个 id。
    不传的话工具会操作到别人的数据 —— 这是多租户最危险的一条路径，
    因为模型完全不知道"用户"是谁，它只看到参数。
    """

    if name == "list_todos":
        items = await todo_service.list_todos(db, user_id=user_id)
        if not items:
            return {"count": 0, "todos": [], "note": "当前没有任何待办"}
        return {
            "count": len(items),
            "todos": [item.model_dump(mode="json") for item in items],
        }

    if name == "create_todo":
        title = (_as_str(args.get("title")) or "").strip()
        if not title:
            return {"error": "title 不能为空"}
        item = await todo_service.create_todo(db, TodoCreate(title=title), user_id=user_id)
        return {"ok": True, "todo": item.model_dump(mode="json")}

    if name == "update_todo":
        todo_id = _as_int(args.get("id"))
        if todo_id is None:
            return {"error": "缺少有效的 id"}
        title = _as_str(args.get("title"))
        done = _as_bool(args.get("done"))
        if title is None and done is None:
            return {"error": "title 和 done 至少要改一个"}
        item = await todo_service.update_todo(
            db,
            todo_id,
            TodoUpdate(title=title, done=done),
            user_id=user_id,
        )
        return {"ok": True, "todo": item.model_dump(mode="json")}

    if name == "delete_todo":
        todo_id = _as_int(args.get("id"))
        if todo_id is None:
            return {"error": "缺少有效的 id"}
        await todo_service.delete_todo(db, todo_id, user_id=user_id)
        return {"ok": True, "deleted_id": todo_id}

    if name == "search_docs":
        query = (_as_str(args.get("query")) or "").strip()
        if not query:
            return {"error": "检索词不能为空"}
        from .rag import retriever

        chunks, ms = await retriever.retrieve(query, top_k=3, user_id=user_id)
        results: list[dict[str, object]] = []
        for i, c in enumerate(chunks):
            results.append(
                {
                    "id": c.id,
                    "doc_id": c.doc_id,
                    "heading": c.heading,
                    "content": c.raw[:200],
                    "relevance": i + 1,
                }
            )
        return {"query": query, "hits": len(results), "chunks": results, "ms": round(ms)}

    if name == "calculator":
        expression = _as_str(args.get("expression")) or ""
        try:
            value = safe_eval(expression)
        except ValueError as exc:
            # 解析失败是"用户输入有问题"，不是程序 bug，
            # 原样告诉模型，它才知道该怎么改表达式
            return {"error": str(exc)}
        # 整数不要显示成 70.0
        pretty: float | int = int(value) if value.is_integer() else value
        return {"expression": expression, "result": pretty}

    return {"error": f"未知工具：{name}"}


async def execute(
    db: aiosqlite.Connection,
    name: str,
    raw_arguments: str,
    user_text: str = "",
    *,
    user_id: str = "",
) -> str:
    """执行一次工具调用，返回给模型看的文本结果。

    永远返回字符串、永不抛异常 —— 失败也是一种"结果"，模型需要看到它。

    user_text 是**用户本轮原话**，S8 的护栏要用它判断"删除是不是用户真的要求的"：
    只看工具参数永远判不出来（攻击者构造的参数也完全合法）。

    user_id 是数据隔离的依据，绝不能让模型从参数里给 ——
    模型给的任何 id 都可能是别人的。
    """
    try:
        parsed = json.loads(raw_arguments) if raw_arguments.strip() else {}
    except json.JSONDecodeError as exc:
        logger.warning("工具 %s 参数不是合法 JSON: %s", name, raw_arguments[:200])
        return json.dumps(
            {"error": f"参数不是合法 JSON：{exc.msg}"},
            ensure_ascii=False,
        )

    if not isinstance(parsed, dict):
        return json.dumps({"error": "参数必须是 JSON 对象"}, ensure_ascii=False)

    args = cast(dict[str, object], parsed)

    # S8：最小权限 + 高危确认。拦下来也返回正常结构，
    # 让模型如实告诉用户"这个操作需要你确认"，而不是静默失败。
    try:
        guard.check_tool(name, args, user_text)
    except ApiError as exc:
        logger.warning("工具 %s 被护栏拦截：%s", name, exc.code)
        return json.dumps(
            {"error": exc.message, "code": exc.code, "guard": True},
            ensure_ascii=False,
        )

    try:
        result = await _run(db, name, args, user_id)
    except ApiError as exc:
        # 典型场景：update/delete 一个不存在的 id
        return json.dumps(
            {"error": exc.message, "code": exc.code},
            ensure_ascii=False,
        )
    except ValidationError as exc:
        # 典型场景：title 超过 200 字
        return json.dumps(
            {"error": f"参数校验失败：{exc.errors()[0]['msg'] if exc.errors() else '未知'}"},
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001 - 工具层必须兜底，否则一次失败会中断整轮对话
        logger.exception("工具 %s 执行异常", name)
        return json.dumps(
            {"error": f"工具执行失败：{type(exc).__name__}"},
            ensure_ascii=False,
        )

    return json.dumps(result, ensure_ascii=False)
