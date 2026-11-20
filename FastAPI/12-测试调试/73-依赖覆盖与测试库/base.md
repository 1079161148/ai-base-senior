# 73 依赖覆盖与测试库 · 完整版（base.md）

> `README.md` 给你能跑的假库 fixture；本文件把「覆盖是怎么被查到的、为什么嵌套依赖自动跟随、为什么 key 必须是同一个函数对象、覆盖会不会影响 schema 与缓存」拆开。学完这章，你能用一套真实路由测遍所有分支，且不在生产代码里留任何测试开关。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0 / pytest 9.2.0（本机实测） |
| 前置 | 第 06 章（依赖注入）、第 71 章（TestClient） |
| 覆盖范围 | `dependency_overrides`、假库、嵌套依赖、配置/鉴权覆盖、清理 |
| 明确不覆盖 | 真实数据库容器、事务回滚隔离、`freezegun` 时间冻结 |
| 学完验收 | 能跑通 `verify.py` 15/15、能解释「为什么只覆盖最内层」 |

## 0. 怎么用这份文件

**依据约定**：`` `[Wn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 覆盖的是「依赖解析结果」
2 机制（第 2 节）    → 查找顺序与嵌套传播
3 API（第 3 节）     → 注册/清理/替身形式
4 边界（第 4 节）    → schema、缓存、异常清理、作用域
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ conftest 分层
```

## 1. 概念：换掉一个节点，整棵树跟着变

```text
端点 → get_repo → get_db → 真实库
                ↓ 覆盖 get_db
端点 → get_repo → get_db → 假库
```

**只有被覆盖的那个节点换了**，其余依赖照常执行。所以：

| 保留真实 | 被替换 |
| --- | --- |
| 路由匹配 | 数据来源 |
| 参数校验（422）| 鉴权结果 |
| 响应序列化 | 配置值 |

## 2. 机制

### 2.1 查找（实测）

```python
main.app.dependency_overrides[main.get_db] = lambda: fake
```

| 写法 | 是否生效 |
| --- | --- |
| `overrides[main.get_db]` | ✅ |
| `overrides["get_db"]` | ❌（静默无效）|
| `overrides[另一个模块里的同名函数]` | ❌ |

dict 的 key 用**对象身份**。实测 `list(app.dependency_overrides)` 打印的是 `get_db / get_settings` 函数对象。

### 2.2 嵌套传播（实测）

只覆盖 `get_db`：

```text
/users → get_repo（未覆盖）→ get_db（已覆盖）→ 假库
结果：1 条假用户
```

`get_repo` 没有出现在 `dependency_overrides` 里，但它拿到的 `db` 已经是假的。**这就是「只覆盖最内层」的原理**。

### 2.3 生成器依赖的覆盖（实测）

原依赖：

```python
def get_db() -> Iterator[dict]:
    db = REAL_DB
    try:
        yield db
    finally:
        pass
```

替身可以直接是普通函数或 `lambda`，FastAPI 不要求同为生成器。**代价**：原依赖的 `finally` 不会执行（因为根本没调用它）。测试里如果要验证清理逻辑，得单独测依赖本身。

## 3. API 逐个拆解

| 操作 | 代码 |
| --- | --- |
| 注册 | `app.dependency_overrides[dep] = fake` |
| 批量清理 | `app.dependency_overrides.clear()` |
| 精确清理 | `app.dependency_overrides.pop(dep, None)` |
| 判断 | `dep in app.dependency_overrides` |
| 当前全部 | `dict(app.dependency_overrides)` |

### 3.1 替身形式（实测）

| 形式 | 是否可用 |
| --- | --- |
| `lambda: fake_dict` | ✅ |
| `def fake_db(): return fake` | ✅ |
| 生成器 `def fake_db(): yield fake` | ✅ |
| `unittest.mock.Mock()` | 签名需匹配，易出错 |

### 3.2 覆盖配置与鉴权（实测）

| 目标 | 效果 |
| --- | --- |
| `get_settings` | `max_items=1` 立刻生效，列表被截断 |
| `get_current_user` | `/me` 免令牌返回 `tester` |

## 4. 边界条件

### 4.1 schema 不受影响（实测）

```text
覆盖前后 openapi()["paths"] 都是 4 条：/users, /users/{user_id}, /me, /config
```

覆盖发生在**请求解析期**，不改路由表。

### 4.2 清理必须无条件执行（实测）

```python
try:
    with overrides(get_db=fake) as c:
        c.get("/users")
        raise RuntimeError("用例中途失败")
except RuntimeError:
    pass
assert app.dependency_overrides == {}      # 实测通过
```

fixture 里写成 `try/finally` 或 `yield` 后清理，异常路径也覆盖到。

### 4.3 作用域

| 作用域 | 风险 |
| --- | --- |
| `function` | 最安全，每次重置 |
| `module` | 同模块共享，注意别相互覆盖 |
| `session` | 容易串状态 |

### 4.4 真实库隔离

实测假库写入后：

```text
假库：{"id": 10, "name": "新用户"}
真实库：{(1, 2)}  ← 不变
```

因为假库是**另一个 dict 对象**。如果替身返回的是同一个对象，就会污染。

### 4.5 与 `use_cache` 的交互

`Depends(..., use_cache=True)` 的缓存在**单次请求内**生效。覆盖后同一请求里多次取到的是同一个替身返回对象。实测未覆盖这一组合，标注为**文档约定**。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| key 用字符串 | 静默失效 | 函数对象 | 实测 |
| 覆盖同名不同对象 | 无效 | `import` 同一对象 | 实测 |
| 忘 `clear()` | 污染后续 | `finally` | 实测 |
| 异常路径不清理 | 泄漏 | `try/finally` | 实测 |
| 直接改模块全局 | 回滚难 | 覆盖依赖 | 实测 |
| 覆盖整个 app | 测不到真实路由 | 只换数据层 | 实测 |
| 假库结构与真库不同 | KeyError | 同构 | 实测 |
| 以为会改 schema | 实际不变 | 放心 | 实测 |
| 只覆盖 `get_repo` 忘 `get_db` | 其实覆盖外层也行 | 覆盖最内层更省 | 实测 |
| 替身返回同一对象 | 污染真库 | 新建对象 | 实测 |
| `Mock` 签名不匹配 | 参数错误 | 明确签名 | `[W2]` |
| 覆盖生成器依赖还指望 `finally` | 不会执行 | 单独测依赖 | 实测 |
| 覆盖 `get_settings` 但配置被缓存 | 旧值 | 清缓存 | 第 66 章 |
| `conftest` 忘了 teardown | 跨文件污染 | `yield` + 清理 | `[W2]` |
| 多个 fixture 抢覆盖 | 后者覆盖前者 | 分层 fixture | 实测 |
| 覆盖后去断言真库 | 数据在假库 | 断响应体 | 实测 |
| 想用覆盖做生产开关 | 全局可变 | 用配置 | `[W1]` |
| 覆盖异步依赖用同步替身 | 类型不匹配 | 匹配 async | 实测 |
| 注册了从未被使用的 key | 静默无效难发现 | 断言 `key in overrides` | 实测 |

## 6. 最佳实践与编码建议

### 6.1 目录

```text
examples/
├── main.py
├── pyproject.toml
├── tests/
│   ├── conftest.py          # 共享 fixture
│   └── test_overrides.py
└── verify.py
```

### 6.2 `conftest.py` 模板

```python
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def fake_db():
    return {"users": {9: {"id": 9, "name": "假用户"}}, "next_id": 10}


@pytest.fixture
def client(fake_db):
    overrides = main.app.dependency_overrides
    overrides[main.get_db] = lambda: fake_db
    overrides[main.get_current_user] = lambda: "tester"
    try:
        with TestClient(main.app) as test_client:
            yield test_client
    finally:
        overrides.clear()
```

### 6.3 分层策略

| 层 | 覆盖什么 |
| --- | --- |
| 会话级 | 无（保持干净）|
| 模块级 | 配置 |
| 函数级 | 数据层、鉴权 |

### 6.4 检查清单

| 检查项 | 原因 |
| --- | --- |
| key 是函数对象 | 否则静默失效 |
| `finally` 清理 | 异常也干净 |
| 假库同构 | 避免 KeyError |
| 替身新建对象 | 不污染真库 |
| 验证 422/404 | 证明路由是真的 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[W1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/testing-dependencies/ | `dependency_overrides` |
| `[W2]` | 文档 | https://docs.pytest.org/en/stable/fixture.html | fixture 与 teardown |
| `[W3]` | 文档 | https://docs.python.org/3/library/unittest.mock.html | `Mock` 用法 |

> **核对状态**：`[W1]`–`[W3]` 为文档链接，**本次未逐页直连复核**；真实数据、假库数据、假库详情、真库不污染、原始鉴权、绕过鉴权、覆盖配置、嵌套跟随、schema 不变、清理恢复、key 为函数对象、lambda 替身、422/404 仍生效、异常清理均为本机实测，`examples/verify.py` 复现 15/15 通过，`pytest -q` 8 用例全绿。`use_cache` 组合、`Mock` 替身、异步依赖覆盖、`conftest` 跨文件**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 覆盖的是依赖解析结果
- [ ] 为什么只覆盖最内层就够
- [ ] 为什么 key 必须是函数对象
- [ ] 覆盖为什么不影响 schema
- [ ] 生成器依赖的 `finally` 去哪了

**能写出（代码层）**：

- [ ] fixture 注册 + 清理
- [ ] 假库同构
- [ ] 覆盖配置
- [ ] 覆盖鉴权
- [ ] `conftest.py` 共享

**能判断（避坑层）**：

- [ ] 看到覆盖无效 → 想到 key 不是同一对象
- [ ] 看到状态互串 → 想到没 `clear`
- [ ] 看到真库被改 → 想到替身返回同一对象
- [ ] 看到 422 也挂了 → 想到可能覆盖了整个 app
- [ ] 看到异常后污染 → 想到 `finally`

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 15/15
- [ ] `uv run pytest -q` 全绿
- [ ] 删掉 `clear()` 后观察哪些用例开始红

## 9. 下一章衔接

第 74 章 `测试 WebSocket 与事件`：`websocket_connect`、收发断言、`WebSocketDisconnect`、lifespan 在测试里的边界。

本章留下的伏笔：

1. 覆盖 `get_db`（73）→ 74 的 WebSocket 端点同样能享受覆盖。
2. fixture 清理（73）→ 74 的广播管理器要 `reset()`。
3. 全局状态隔离（72、73）→ 74 的连接池是另一个全局状态。