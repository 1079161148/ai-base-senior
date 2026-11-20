# 78 毕业项目（二）· 生产化改造 · 完整版（base.md）

> `README.md` 给你六处改造的对照表；本文件把「事务依赖为什么没写 commit 也能提交、异常怎么穿透到 rollback、`SecretStr` 的三个泄露面、`BaseHTTPMiddleware` 的代价、静态扫描该查什么」拆开。学完这章，你能把任何一个「能跑的 demo」改造成能上生产的服务。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0 / pydantic-settings 2.16（本机实测） |
| 前置 | 第 57 章（事务）、第 66 章（配置）、第 73 章（依赖覆盖）、第 75 章（日志） |
| 覆盖范围 | 配置外置、日志、中间件、SQLite 事务、依赖注入、静态卫生 |
| 明确不覆盖 | 连接池、迁移工具、分布式事务、APM |
| 学完验收 | 能跑通 `verify.py` 23/23 与 `pytest -q` 8 用例 |

## 0. 怎么用这份文件

**依据约定**：`` `[b]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 六处改造的因果
2 机制（第 2 节）    → 事务依赖与异常穿透
3 API（第 3 节）     → 配置/日志/中间件
4 边界（第 4 节）    → SQLite 线程、SecretStr、静态扫描
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 分层与清单
```

## 1. 概念：六处改造各自的因果

| 改造 | 不做的后果 | 做完的收益 |
| --- | --- | --- |
| 配置外置 | 换环境要改代码、密钥进仓库 | 一处切换 |
| 日志 | 线上只能看 500 数量 | 能定位到具体请求 |
| 事务边界 | 写一半失败留脏数据 | 要么全成要么全不成 |
| 依赖注入 | 测试要改全局变量 | 覆盖即可 |
| 中间件 | 无法关联跨服务调用 | 请求 ID 全链路 |
| 静态卫生 | 裸 `except` 吞错、SQL 拼接 | 可审计 |

## 2. 机制

### 2.1 事务依赖（实测）

```python
try:
    yield conn
    conn.commit()      # 端点正常返回
except Exception:
    conn.rollback()    # 端点抛任何异常
    raise
finally:
    conn.close()
```

实测 `POST /api/v1/todos/_tx`：

```text
响应 409 {"error": {"code": "tx_demo", ...}}
表内行数 0
```

**关键点**：`AppError` 继承 `Exception`，所以 `except Exception` 能捕获；捕获后**必须 `raise`**，否则异常被吞、响应变成 200。

### 2.2 异常穿透顺序

```text
端点 raise AppError
  → 依赖生成器收到异常（rollback）
  → 异常继续上抛
  → FastAPI 匹配 AppError 处理器
  → 409 响应
```

如果是 `HTTPException`，同理 rollback 后由 `http_exception_handler` 出响应。

### 2.3 `BaseHTTPMiddleware` 的代价

| 项 | 说明 |
| --- | --- |
| 优点 | 类写法、可传参（`version`/`slow_ms`） |
| 代价 | 多一层 anyio task，流式响应会变慢 |
| 替代 | `@app.middleware("http")`（函数式，性能略好） |

本章用类写法是为了把 `version`/`slow_ms` 作为构造参数注入，避免全局变量。

### 2.4 请求 ID 的两处落点

```text
response.headers["X-Request-ID"]       ← 客户端可回传
request.state.request_id               ← 错误处理器可读
logger extra={"request_id": ...}       ← 日志可筛
```

实测 8 位 hex，传入 `trace-9` 时原样透传。

## 3. API 逐个拆解

### 3.1 配置项

| 变量 | 类型 | 校验 |
| --- | --- | --- |
| `APP_ENV` | `Literal` | 只能是 `dev/test/prod` |
| `APP_DB_PATH` | `str` | 无 |
| `APP_TOKEN` | `SecretStr` | 无 |
| `APP_PAGE_SIZE_MAX` | `int` | `ge=1, le=1000` |
| `APP_LOG_LEVEL` | `Literal` | 四档 |
| `APP_SLOW_MS` | `int` | `ge=1` |

非法值会在**启动时**就失败（fail fast），而不是运行到一半才炸。

### 3.2 依赖树

```text
get_settings (lru_cache)
  ├── get_conn ──→ get_repo ──→ 端点
  └── get_current_user ──→ Writer
pagination / filters（纯参数聚合）
```

| 依赖 | 可覆盖（测试） |
| --- | --- |
| `get_settings` | ✅ 换库/换令牌 |
| `get_conn` | ✅ 换内存库 |
| `get_repo` | ✅ 换假仓储 |
| `get_current_user` | ✅ 绕过鉴权 |

### 3.3 日志格式

```text
23:43:32 INFO [trace-9] app.request request method=GET path=/api/v1/todos status=200 elapsed_ms=2.36
```

| 段 | 来源 |
| --- | --- |
| `[trace-9]` | `RequestIdFilter` 补的 `request_id` |
| `app.request` | logger 名 |
| `method/path/status` | `%s` 参数 |
| `elapsed_ms` | `perf_counter` 差值 |

## 4. 边界条件

### 4.1 SQLite 的线程限制（实测相关）

`sqlite3.connect(..., check_same_thread=False)` 是必须的：FastAPI 把同步端点丢到线程池，连接可能在不同线程用。

代价：失去线程安全检查，必须保证**一个请求一个连接**（本设计满足）。

### 4.2 `SecretStr` 的三个泄露面（实测）

```text
repr(settings)                    → token=SecretStr('**********')
str(settings.token)               → '**********'
settings.model_dump(mode="json")  → {'token': '**********'}
settings.token.get_secret_value() → 'verify-token-123'   ← 唯一正确取值
```

**三大坑**：把 `SecretStr` 直接拼进 URL（得到掩码）、把它传给 `sqlite3`（拿到 `SecretStr` 对象）、JSON 序列化再读回（掩码被当真实值）。

### 4.3 `lru_cache` 与测试

`get_settings()` 被 `@lru_cache` 缓存。测试里改完 `os.environ` 必须：

```python
get_settings.cache_clear()
```

本章 `verify.py` 采用更彻底的做法：**在 `import main` 之前**设好环境变量，让模块级 `settings` 一开始就正确。

### 4.4 静态扫描查什么

| 检查 | 正则/方法 | 为什么 |
| --- | --- | --- |
| 裸 `except` | `except\s*:` | 吞掉 `KeyboardInterrupt` |
| `except Exception: pass` | 多行正则 | 静默失败 |
| 硬编码密钥 | 搜字面量 | 泄露/换环境难 |
| SQL 拼接 | 搜 `%s`、`.format(`、`+` | 注入面 |

实测 10 个源文件全部干净。

### 4.5 探针与库

`/healthz` 不查库。理由见第 76 章：库抖动触发重启会雪崩。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 端点手动 `commit()` | 中途失败留脏数据 | 依赖里统一提交 | 实测 |
| `except` 里不 `raise` | 异常被吞返 200 | `raise` 继续抛 | 实测 |
| 令牌硬编码 | 换环境改代码 | `SecretStr` + env | 实测 |
| `SecretStr` 直接 `str()` | 拿到掩码 | `.get_secret_value()` | 实测 |
| 每次请求新建连接不关 | 句柄泄漏 | `finally: close()` | 实测 |
| SQLite 跨线程 | `ProgrammingError` | `check_same_thread=False` | 实测 |
| SQL 用 f-string 拼用户输入 | 注入 | `?` 占位 | 实测 |
| 日志用 f-string 拼 | 无 `extra` | `%s` + `extra` | 实测 |
| 中间件吞异常 | 500 无请求 ID | 记日志后 `raise` | 实测 |
| 改环境变量不 `cache_clear` | 读到旧配置 | `cache_clear()` | 第 66 章 |
| `configure_logging` 重复调用 | 日志翻倍 | `force=True` | 实测 |
| 探针查库 | 库抖动引发重启 | 只查进程 | 第 76 章 |
| 事务里做网络请求 | 锁持有过久 | 事务外调用 | `[b3]` |
| `include_in_schema=False` 但不鉴权 | 内部端点被调用 | 加鉴权 | 实测 |
| SQLite 存 `bool` | 读出 `0/1` | `bool(row)` | 实测 |
| 测试共用 db | 数据串 | 每例 `reset_db()` | 实测 |
| 环境变量在 import 后设 | 不生效 | `conftest.py` 先设 | 实测 |
| `sqlite_sequence` 不重置 | id 一直涨 | `DELETE FROM sqlite_sequence` | 实测 |
| `connect` 不设 `row_factory` | 只能按下标取值 | `conn.row_factory = sqlite3.Row` | 实测 |

## 6. 最佳实践与编码建议

### 6.1 目录

```text
examples/
├── config.py         # 配置
├── db.py             # 连接 + 事务依赖
├── repo.py           # SQL
├── deps.py           # 依赖装配
├── models.py         # 契约
├── errors.py         # 错误契约
├── middleware.py     # 可观测
├── logging_setup.py  # 日志
├── todos_router.py   # 端点
├── main.py           # 装配
├── tests/{conftest.py,test_prod.py}
└── verify.py
```

### 6.2 分层规则

| 层 | 可以 import | 禁止 |
| --- | --- | --- |
| `repo` | sqlite3、models | fastapi、request |
| `deps` | 全部内层 | 业务逻辑 |
| `router` | deps、models、errors | 直接 sqlite3 |
| `main` | 全部 | 业务逻辑 |

### 6.3 上生产前清单

| 项 | 检查方式 |
| --- | --- |
| 无硬编码 | 静态扫描 |
| 无裸 except | 静态扫描 |
| SQL 参数绑定 | 静态扫描 + review |
| 事务边界 | `/_tx` 用例 |
| 配置可外置 | 换 env 跑一次 |
| 日志可关联 | 看请求 ID |
| 探针不查依赖 | 手动停库 |
| 密钥不进日志 | 搜日志输出 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[b1]` | 文档 | https://docs.pydantic.dev/latest/concepts/pydantic_settings/ | `SecretStr`/env |
| `[b2]` | 文档 | https://docs.python.org/3/library/sqlite3.html | 事务与 `Row` |
| `[b3]` | 文档 | https://www.starlette.io/middleware/ | `BaseHTTPMiddleware` |

> **核对状态**：`[b1]`–`[b3]` 为文档链接，**本次未逐页直连复核**；配置来自环境变量、`SecretStr` 掩码、探针不查库、请求 ID 生成与透传、版本头、一行日志、慢请求 WARNING、创建/分页/过滤/部分更新/删除、404/401/422/500 契约、事务提交、**事务回滚（409 且 0 行）**、无裸 except（10 文件）、无硬编码密钥、SQL 全 `?` 占位、OpenAPI 4 路径均为本机实测，`examples/verify.py` 复现 23/23 通过，`pytest -q` 8 用例全绿。连接池、迁移、并发压测、WAL、分布式事务**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 六处改造各自解决什么
- [ ] 事务依赖为什么不用写 `commit`
- [ ] `except` 里为什么必须 `raise`
- [ ] `SecretStr` 的三个泄露面
- [ ] `BaseHTTPMiddleware` 的代价

**能写出（代码层）**：

- [ ] 事务依赖
- [ ] 参数绑定 SQL
- [ ] 请求 ID 中间件
- [ ] 一行日志 formatter
- [ ] 静态扫描

**能判断（避坑层）**：

- [ ] 看到脏数据 → 想到事务边界
- [ ] 看到 200 但实际失败 → 想到异常被吞
- [ ] 看到令牌泄露 → 想到 `SecretStr`
- [ ] 看到环境变量不生效 → 想到 `cache_clear`
- [ ] 看到 SQL 拼接 → 指出注入面

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 23/23
- [ ] `uv run pytest -q` 全绿
- [ ] 换 `APP_DB_PATH` 起服务，数据落到新文件

## 9. 下一章衔接

第 79 章 `毕业项目（三）：验收与复盘`：79 条分维度验收、性能与安全复核、复盘文档。

本章留下的伏笔：

1. 六处改造（78）→ 79 把每处变成可勾选的验收项。
2. 静态扫描（78）→ 79 扩展成安全复核的一部分。
3. 事务回滚用例（78）→ 79 的「数据与事务」维度。