# 55 数据库连接与生命周期 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「`lifespan` 在 ASGI 的哪一层、连接为什么必须跨线程、`to_thread` 的真实代价、SQLite 的并发模型」拆开。学完这章，你要能判断一个「数据库偶发报错」是连接问题、线程问题还是事务问题。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 50 章（中间件）、第 37 章（依赖缓存） |
| 覆盖范围 | `lifespan`、`app.state`、`sqlite3`、`to_thread`、连接关闭 |
| 明确不覆盖 | SQLAlchemy 全量、连接池实现、读写分离、迁移工具 |
| 学完验收 | 能跑通 `verify.py` 14/14、能解释三个报错的成因 |

## 0. 怎么用这份文件

**依据约定**：`` `[Dn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 生命周期归属
2 机制（第 2 节）    → lifespan 调用时机
3 API（第 3 节）     → 连接与线程
4 边界（第 4 节）    → 三种报错
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 生产接法
```

## 1. 概念：连接是「应用级资源」

| 资源 | 生命周期 | 放哪 |
| --- | --- | --- |
| 连接/池 | 应用启动到关闭 | `lifespan` + `app.state` |
| 事务 | 单个请求 | `yield` 依赖（第 57 章）|
| 游标 | 单条语句 | 函数内局部 |

放错层级的后果：连接放请求级 → 每次握手开销；事务放应用级 → 一个请求回滚掉别人的写入。

## 2. 机制：`lifespan` 被谁调用

```text
uvicorn 启动
  → app(scope={"type": "lifespan"}, ...)
    → lifespan 生成器第一次 next()   ← yield 之前
      ... 处理请求 ...
    → 第二次 next() / aclose()       ← yield 之后
uvicorn 关闭
```

| 事实 | 说明 |
| --- | --- |
| 用 `@asynccontextmanager` | `yield` 前是启动，后是清理 |
| 异常启动 | 也要走 `finally` |
| `TestClient` | 只在 `with` 块里触发（实测）|
| `@app.on_event` | 已废弃（实测有警告）|

### 2.1 实测三种状态

| 场景 | `app.state.db` | 端点结果 |
| --- | --- | --- |
| 无 `with` 的 TestClient | 不存在 | `AttributeError`（首个请求）|
| `with` 内 | 打开 | 200 |
| `with` 结束后 | 存在但已关闭 | `ProgrammingError` |

## 3. API 逐个拆解

### 3.1 `sqlite3.connect`

| 参数 | 作用 | 必需性 |
| --- | --- | --- |
| `check_same_thread=False` | 允许跨线程 | `to_thread` 下**必需** |
| `timeout=5.0` | 等锁超时 | 并发写建议调大 |
| `isolation_level=None` | 自动提交模式 | 手动控事务时用 |
| `uri=True` | 支持 `file:` URI | 共享内存库时需要 |

### 3.2 `row_factory`

不设时 `row[0]`；设 `sqlite3.Row` 后可 `row["name"]` 和 `dict(row)`。

### 3.3 `asyncio.to_thread`

| 项 | 说明 |
| --- | --- |
| 默认线程池 | `min(32, cpu+4)` |
| 开销 | 每次一次线程调度，微秒级 |
| 适合 | 短查询 |
| 不适合 | 极长查询（占满线程池）|

## 4. 边界条件

### 4.1 线程亲和（实测）

```text
sqlite3.ProgrammingError: SQLite objects created in a thread can only be
used in that same thread. The object was created in thread id 52068 and
this is thread id 44684.
```

`to_thread` 每次可能用不同线程，所以必须 `check_same_thread=False`。

**代价**：关掉检查后，同一个连接被多线程同时写会不可预期。SQLite 的写是库级锁，生产建议**单写线程**或每请求一个连接。

### 4.2 关闭后使用（实测）

```text
sqlite3.ProgrammingError: Cannot operate on a closed database.
```

原因通常是：连接存全局、测试里重复 `with`、或热重载时旧对象残留。

### 4.3 `:memory:` 不共享（实测）

两次 `sqlite3.connect(":memory:")` 得到两个独立库，第二个查第一个建的表：

```text
sqlite3.OperationalError: no such table: t
```

要共享用：

```python
sqlite3.connect("file:memdb1?mode=memory&cache=shared", uri=True)
```

且必须保持至少一个连接打开，否则库被销毁。

### 4.4 唯一冲突翻译

`IntegrityError` 是数据库语义，直接冒出去就是 500。要显式翻译：

```python
try:
    ...
except sqlite3.IntegrityError as exc:
    db.rollback()
    raise HTTPException(409, "名称已存在") from exc
```

**注意**：`IntegrityError` 后必须 `rollback()`，否则连接处于失败事务状态。

### 4.5 健康检查

`/health` 只返回 `{"ok": true}` 是假健康。要真执行 `SELECT 1` 或 `COUNT(*)`，失败返回 503。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| TestClient 不加 `with` | lifespan 不跑（实测）| `with TestClient(...)` | 实测 |
| 默认 `check_same_thread` | 线程池里 `ProgrammingError`（实测）| `False` | 实测 |
| `async def` 里直接查库 | 阻塞事件循环 | `to_thread` | `[D1]` |
| `:memory:` 想共享 | 表不存在（实测）| `cache=shared` | 实测 |
| 建表不 `commit` | 表丢失 | 显式提交 | `[D2]` |
| `IntegrityError` 不 rollback | 后续语句全失败 | `rollback()` | `[D2]` |
| `IntegrityError` 直冒 | 500 | 翻译 409 | 实测 |
| 用 `@app.on_event` | 废弃警告（实测）| `lifespan` | 实测 |
| 连接放模块全局 | 测试串、多进程失效 | `app.state` | `[D1]` |
| 只在 `yield` 后关闭 | 启动异常泄漏 | `try/finally` | `[D3]` |
| 每请求新建连接 | 慢 | 复用 | `[D1]` |
| 忘 `row_factory` | 只能下标 | `sqlite3.Row` | `[D2]` |
| f-string 拼 SQL | 注入 | 参数化 | `[D4]` |
| 长读事务不关 | 写被锁 | 尽快提交 | `[D2]` |
| 多线程同连接写 | 数据竞争 | 单写线程/每请求连接 | `[D2]` |
| 健康检查不碰库 | 假健康 | 真查询 | `[D3]` |
| 测试用生产库文件 | 数据污染 | 临时目录/内存 | 第 71 章 |
| 连接在 `lifespan` 里被 `close` 两次 | `ProgrammingError` | 幂等或只关一次 | `[D2]` |
| 不设 `busy_timeout` 就当并发安全 | 并发写直接 `database is locked` | `PRAGMA busy_timeout` | `[D2]` |

## 6. 最佳实践与编码建议

### 6.1 分层位置

```text
main.py        → lifespan（建连接、建表、注册路由）
db.py          → connect()、事务依赖
repository.py  → 纯 SQL（第 56 章）
service.py     → 业务规则
router.py      → HTTP 语义
```

### 6.2 生产接法

| 场景 | 建议 |
| --- | --- |
| SQLite 单机 | `check_same_thread=False` + `to_thread` + `busy_timeout` |
| PostgreSQL | `asyncpg`/SQLAlchemy async + 连接池 |
| 高并发写 | 换库，别硬扛 SQLite |

### 6.3 测试模式

```python
with TestClient(app) as client:
    ...
```

每个测试函数一个 `with`，或用 fixture：

```python
@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
```

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[D1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/events/ | `lifespan` |
| `[D2]` | 文档 | https://docs.python.org/3/library/sqlite3.html | sqlite3 语义 |
| `[D3]` | 文档 | https://www.starlette.io/lifespan/ | lifespan 协议 |
| `[D4]` | 指南 | https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html | 参数化 |

> **核对状态**：`[D1]`–`[D4]` 为官方文档/指南链接，**本次未逐页直连复核**；`with` 触发 lifespan、无 `with` 不触发、建表、增查、409 翻译、422、健康检查、关闭后报错、线程亲和、`check_same_thread=False`、`:memory:` 不共享、`on_event` 废弃均为本机实测，`examples/verify.py` 复现 14/14 通过。连接池、`aiosqlite`、并发写竞争**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 连接/事务/游标的生命周期归属
- [ ] `lifespan` 在 ASGI 的调用时机
- [ ] 为什么 `to_thread` 必须配 `check_same_thread=False`
- [ ] `:memory:` 为什么不共享
- [ ] `IntegrityError` 后为什么必须 rollback

**能写出（代码层）**：

- [ ] 完整 `lifespan`
- [ ] `to_thread` 包裹的仓储函数
- [ ] 409 翻译
- [ ] 真查库的健康检查
- [ ] `with TestClient` 的测试

**能判断（避坑层）**：

- [ ] 看到 `AttributeError: 'State' object has no attribute 'db'` → 指出没进 `with`
- [ ] 看到线程亲和报错 → 指出 `check_same_thread`
- [ ] 看到 `Cannot operate on a closed database` → 指出连接生命周期
- [ ] 看到 `:memory:` 共享假设 → 指出每连接独立
- [ ] 看到 `on_event` → 指出已废弃

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `uvicorn` 启动后 `curl /health`
- [ ] 停服务看连接是否释放

## 9. 下一章衔接

第 56 章 `仓储层分层`：把 SQL 从路由里搬到 `repository`，用 `service` 放业务规则，路由只做 HTTP 语义；讲「为什么路由里不该出现 `SELECT`」「依赖注入怎么把仓储交给路由」「分层的代价」。

本章留下的伏笔：

1. `app.state.db`（55）→ 仓储层从依赖拿连接（56）。
2. `IntegrityError` 翻译（55）→ 服务层统一异常（56）。
3. 事务边界（57）→ 仓储不提交，由依赖统一提交。