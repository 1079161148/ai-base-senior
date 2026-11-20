# 56 仓储层分层 · 完整版（base.md）

> `README.md` 给你能跑的分层示例；本文件把「每层的判据怎么定、依赖注入怎么串、领域异常怎么映射、分层什么时候是过度设计」拆开。学完这章，你要能判断一段代码该放哪层，以及什么时候不该分层。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 55 章（连接与生命周期）、第 37 章（依赖缓存） |
| 覆盖范围 | router/service/repository 三层、`get_db` 依赖、领域异常、`dependency_overrides` |
| 明确不覆盖 | DDD 聚合/值对象全量、CQRS、ORM 映射、多数据源 |
| 学完验收 | 能跑通 `verify.py` 14/14、能说清每层边界 |

## 0. 怎么用这份文件

**依据约定**：`` `[Rn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 每层的变化理由
2 机制（第 2 节）    → 依赖链怎么串
3 API（第 3 节）     → 组装函数
4 边界（第 4 节）    → 可替换性、路由顺序、连接关闭
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 何时不该分层
```

## 1. 概念：一层一个变化理由

| 层 | 变化原因 | 判据 |
| --- | --- | --- |
| `router` | HTTP 契约变了（路径/状态码/字段）| 只处理 `Request`/`Response` |
| `service` | 业务规则变了 | 不 import `sqlite3`、不 import `fastapi` |
| `repository` | SQL/存储变了 | 不 import `fastapi` |

**单层变化**：改 HTTP 不碰 SQL；换库不碰路由。

## 2. 机制：依赖链怎么串

```text
请求
 → get_db()           每请求一个连接（yield 依赖）
   → get_repository(conn)
     → get_service(repo)
       → 端点函数(service)
```

| 事实 | 说明 |
| --- | --- |
| 依赖缓存 | 同请求内 `get_db` 只执行一次（第 37 章）|
| 组装点 | 只有 `get_repository` 知道具体实现 |
| 替换点 | `app.dependency_overrides[get_repository]` |

实测替换：

```python
main.app.dependency_overrides[get_repository] = FakeRepository
# GET /items → [{"id": 42, "name": "假数据", "price": 0}]
```

**路由与 service 代码一行没改**——这就是分层的可验证收益。

## 3. API 逐个拆解

| 组装函数 | 依赖 | 返回 |
| --- | --- | --- |
| `get_db` | 无 | `Iterator[Connection]` |
| `get_repository` | `Depends(get_db)` | `ItemRepository` |
| `get_service` | `Depends(get_repository)` | `ItemService` |

### 3.1 领域异常映射

| 领域异常 | HTTP | 位置 |
| --- | --- | --- |
| `DuplicateItemError` | 409 | router 里 `except` 翻译 |
| `ItemNotFoundError` | 404 | 同上 |
| `sqlite3.IntegrityError` | 500（兜底）| 不该出现，service 先判 |

**注意**：router 里只捕获**具体的**领域异常，不要 `except Exception`。

### 3.2 `response_model` 放哪

放 router，不放 repository。仓储返回领域模型，router 用 `response_model` 控制输出字段（第 21 章）。

## 4. 边界条件

### 4.1 路由顺序（实测）

```text
GET /items/count   → 422 {"type": "int_parsing", "loc": ["path", "item_id"]}
```

原因：`/{item_id}` 先注册，`count` 被当路径参数，`int` 解析失败 → 422。

| 写法 | 结果 |
| --- | --- |
| `GET /items/count` | 422 |
| `GET /items/_/count` | 200 |

**结论**：静态路径要写在动态路径之前，或者用不同段数避开。

### 4.2 连接不关闭（实测）

```python
with sqlite3.connect(DB_FILE) as conn:   # 只提交事务，不关闭
    ...
```

Windows 上后续 `unlink` 报：

```text
PermissionError: [WinError 32] 另一个程序正在使用此文件
```

正确写法：

```python
conn = connect()
try:
    ...
finally:
    conn.close()
```

### 4.3 跨请求可见性

56 章在 `repository.add/delete` 里 `commit()`。好处：简单、跨请求可见。
坏处：一次请求多次写会多次提交，事务边界碎——第 57 章上移到依赖层。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 路由里写 SQL | 换库改路由 | 移到 repository | 实测 |
| 路由里判重名 | 规则散落 | 移到 service | 实测 |
| service 抛 HTTP 异常 | 业务耦合 HTTP | 领域异常 | 实测 |
| 仓储返回 `Row`/`dict` | 泄漏存储细节 | 返回模型 | `[R1]` |
| `with sqlite3.connect()` 当关闭 | **不关闭**（实测）| `try/finally` | 实测 |
| 静态路径在动态后 | 422（实测）| 顺序调整 | 第 09 章 |
| 仓储里 `commit` | 事务边界碎 | 上移到依赖 | 第 57 章 |
| 每层重复校验 | 冗余 | 入口一次 | `[R1]` |
| 加 5 层抽象 | 难读 | 三层足够 | `[R2]` |
| 测试连真库 | 污染 | override | 实测 |
| `get_db` 不 close | 泄漏 | `finally` | 实测 |
| `except Exception` 全兜 | 掩盖错误 | 只捕领域异常 | `[R3]` |
| service import fastapi | 可测性下降 | 纯函数 | `[R1]` |
| 用 ORM 实体当响应模型 | 泄露字段 | 独立 schema | 第 21 章 |
| 事务放 repository | 跨仓储操作无法原子 | 依赖层 | 第 57 章 |
| 一个仓储塞 50 个方法 | 上帝对象 | 按聚合拆 | `[R2]` |
| 领域异常不带上下文 | 无法定位 | 带 id/name | `[R3]` |
| 分层后没写测试 | 收益没兑现 | override + 单测 | 第 71 章 |
| 路由直接调仓储绕过 service | 业务规则失效 | 只经 service | `[R1]` |

## 6. 最佳实践与编码建议

### 6.1 何时不该分层

| 场景 | 建议 |
| --- | --- |
| 单表 CRUD、3 个端点 | 直接 router + SQL 也行 |
| 业务规则复杂 | 值得 service |
| 要换存储/多数据源 | 必须 repository |
| 团队 > 3 人 | 分层降低冲突 |

**分层的代价**：多用 3 个文件、多一层间接、调试要跳转。收益是**可替换与可测**——没有这两点需求时，分层是负担。

### 6.2 文件模板

```python
# db.py
def get_db() -> Iterator[Connection]: ...

# repository.py
class XRepository:
    def __init__(self, conn: Connection) -> None: ...

# service.py
class XService:
    def __init__(self, repository: XRepository) -> None: ...

# router.py
def get_repository(conn: Annotated[Connection, Depends(get_db)]) -> XRepository: ...
def get_service(repo: Annotated[XRepository, Depends(get_repository)]) -> XService: ...
```

### 6.3 静态判据（可进 CI）

```python
source = Path("repository.py").read_text()
assert "HTTPException" not in source
assert "APIRouter" not in source
```

本章 `verify.py` 就是这么做的，比「靠自觉」可靠。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[R1]` | 文章 | https://fastapi.tiangolo.com/zh/tutorial/bigger-applications/ | 分层与 `APIRouter` |
| `[R2]` | 文章 | https://martinfowler.com/eaaCatalog/repository.html | Repository 模式 |
| `[R3]` | 文档 | https://fastapi.tiangolo.com/zh/tutorial/handling-errors/ | 异常处理 |

> **核对状态**：`[R1]`–`[R3]` 为官方文档/模式原文链接，**本次未逐页直连复核**；三层行为、重名 409、不存在 404、删除 204/404、路由顺序 422、`/_/count`、仓储替换、静态判据、OpenAPI 路径均为本机实测，`examples/verify.py` 复现 14/14 通过。ORM、多数据源、并发事务**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 每层的变化理由与判据
- [ ] 依赖链的组装点
- [ ] 领域异常为什么不能是 HTTP 异常
- [ ] 分层的代价
- [ ] 何时不该分层

**能写出（代码层）**：

- [ ] 三个组装函数
- [ ] 领域异常 + router 翻译
- [ ] `dependency_overrides` 测试
- [ ] 静态判据脚本

**能判断（避坑层）**：

- [ ] 看到路由里 SQL → 指出该移
- [ ] 看到 service 抛 `HTTPException` → 指出耦合
- [ ] 看到 `/items/count` → 指出 422 风险
- [ ] 看到 `with sqlite3.connect()` → 指出不关连接
- [ ] 看到仓储 `commit` → 指出事务边界

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] 用 `dependency_overrides` 写一个隔离测试
- [ ] `curl /items/count` 看 422

## 9. 下一章衔接

第 57 章 `事务边界`：把 `commit/rollback` 上移到 `yield` 依赖，讲「一次请求一个事务」「异常时自动回滚」「`yield` 依赖的执行顺序与异常传播」「多个仓储共享同一事务」。

本章留下的伏笔：

1. 仓储里的 `commit()`（56）→ 57 上移。
2. `get_db` 的 `finally`（56）→ 57 加 `rollback`。
3. 领域异常（56）→ 57 里触发回滚。