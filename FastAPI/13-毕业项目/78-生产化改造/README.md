# 78 毕业项目（二）：生产化改造

## 一句话结论

从「能跑」到「能上生产」是六处改造：**配置外置**（`SecretStr` 令牌不再硬编码）、**结构化日志**（一行一请求 + 请求 ID）、**中间件**（耗时/版本头）、**SQLite + 事务边界**（在依赖里 commit/rollback，端点不写 `commit`）、**依赖注入**（`repo`/分页/过滤/鉴权全部可覆盖）、**错误契约加日志**。实测 23/23，其中最有价值的两条：把库路径换成环境变量后 `settings.db_path` 立刻跟着变、`SecretStr` 在 `repr` 里是 `**********`；以及**事务回滚**——`POST /_tx` 先 `INSERT` 再抛 `AppError`，返回 409 且表里 0 行。另外三条静态扫描也通过：10 个源文件无裸 `except`、令牌只出现在 `config.py` 默认值、`repo.py` 全部 `?` 占位。

## 最小可运行案例

```python
# db.py：事务放在依赖里
def get_conn(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()          # 正常返回 → 提交
    except Exception:
        conn.rollback()        # 任何异常 → 回滚
        raise
    finally:
        conn.close()
```

```python
# config.py：令牌不再硬编码
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")
    db_path: str = "todos.db"
    token: SecretStr = SecretStr("demo-token")
    page_size_max: int = 100
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    slow_ms: int = 50
```

```python
# middleware.py：一行一请求 + 请求 ID
class ObserveMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:8]
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.log(
            logging.WARNING if elapsed >= self.slow_ms else logging.INFO,
            "request method=%s path=%s status=%s elapsed_ms=%.2f",
            request.method, request.url.path, response.status_code, elapsed,
            extra={"request_id": request_id},
        )
        return response
```

## 怎么跑

```powershell
cd "13-毕业项目\78-生产化改造\examples"
uv sync
uv run python verify.py
uv run pytest -q

# 手工起服务（注意必须给令牌）
$env:APP_DB_PATH="todos.db"; $env:APP_TOKEN="my-token"
uvicorn main:app --reload
```

预期输出：

```text
[PASS] 配置来自环境变量 -> ch78_xxxx/todos.db
[PASS] 密钥掩码 -> token → **********
[PASS] 探针不查库 -> 200 / todos.db
[PASS] 请求 ID 生成 -> 70319345
[PASS] 请求 ID 透传 -> trace-9
[PASS] 版本头 -> 1.0.0
[PASS] 一行日志 -> method/path/status/request_id 齐全
[PASS] 慢请求 WARNING -> request method=POST path=/api/v1/todos status=
[PASS] 创建 201 -> 201 / id=1
[PASS] 分页 -> 3 条 / 2 页 / 首页 2 条
[PASS] 过滤 -> done/priority/q 都生效
[PASS] 部分更新 -> 只改 done
[PASS] 删除 -> 204 → 404
[PASS] 404 契约 -> not_found
[PASS] 401 用配置令牌 -> demo-token 已失效 / 无令牌 401
[PASS] 422 契约 -> validation_error / body.title
[PASS] 500 契约 -> internal_error / 无堆栈
[PASS] 事务提交 -> 已落库
[PASS] 事务回滚 -> 409 / 表里 0 行
[PASS] 无裸 except -> 10 个文件干净
[PASS] 无硬编码密钥 -> 仅 config 有默认值
[PASS] SQL 参数绑定 -> 全部 ? 占位
[PASS] OpenAPI 完整 -> 4 条路径

结果：23/23 通过
```

`pytest -q` 另外 8 个用例全绿。

## 改造对照表

| 维度 | 第 77 章 | 第 78 章 |
| --- | --- | --- |
| 令牌 | `DEMO_TOKEN` 常量 | `settings.token`（`SecretStr`） |
| 数据 | 模块级 `store` 单例 | `Depends(get_repo)` |
| 持久化 | 内存 dict | SQLite 文件 |
| 事务 | 无 | 依赖里 commit/rollback |
| 配置 | 无 | `config.py` + 环境变量 |
| 日志 | 无 | 一行一请求 + 请求 ID |
| 中间件 | 无 | 请求 ID / 耗时 / 版本 |
| 错误 | 无日志 | `AppError` 记 WARNING |
| 测试 | 直接 import store | 覆盖 `get_settings` |

| 环境变量 | 作用 | 默认 |
| --- | --- | --- |
| `APP_ENV` | `dev/test/prod` | `dev` |
| `APP_DB_PATH` | SQLite 路径 | `todos.db` |
| `APP_TOKEN` | 写操作令牌 | `demo-token` |
| `APP_PAGE_SIZE_MAX` | 每页上限 | 100 |
| `APP_LOG_LEVEL` | 日志级别 | `INFO` |
| `APP_SLOW_MS` | 慢请求阈值 | 50 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 端点里手动 `commit()` | 抛异常时脏数据 | 依赖里统一提交 |
| `except` 里只 `rollback` 不 `raise` | 异常被吞，返 200 | `raise` 继续抛 |
| 令牌硬编码 | 换环境要改代码 | `SecretStr` + 环境变量 |
| `SecretStr` 直接 `str()` | 拿到掩码当令牌用 | `.get_secret_value()` |
| 每个请求新建连接不关 | 句柄泄漏 | `finally: close()` |
| `sqlite3` 跨线程 | `ProgrammingError` | `check_same_thread=False` |
| SQL 用 f-string 拼用户输入 | 注入 | `?` 占位 |
| 日志用 f-string 拼 | 无 `extra`、无关联 | `%s` + `extra` |
| 中间件里吞异常 | 500 无请求 ID | 记日志后 `raise` |
| `lru_cache` 的配置改环境变量不生效 | 读到旧值 | `cache_clear()` |
| `configure_logging` 重复调用 | 日志翻倍 | `force=True` |
| 探针里查库 | 库抖动引发重启 | 只查进程 |
| 事务里做网络请求 | 锁持有过久 | 事务外调用 |
| `include_in_schema=False` 但忘了排除测试 | 内部端点被外部调用 | 加鉴权 |
| SQLite 存 `bool`/`datetime` | 读出类型不对 | 手动转换 |
| 测试之间共用一个 db 文件 | 数据串 | 每例 `reset_db()` |
| 环境变量在 import 后设置 | 不生效 | `conftest.py` 里设 |
| `sqlite_sequence` 不重置 | id 一直增长 | `DELETE FROM sqlite_sequence` |

## 毕业自查

- [ ] 能说出六处改造各自解决什么问题
- [ ] 能证明事务回滚（`/_tx` 后表为空）
- [ ] 能用环境变量换库、换令牌
- [ ] 能看到一行日志里的请求 ID
- [ ] 能写静态扫描（无裸 except / 无硬编码 / 参数绑定）
- [ ] 动手题一：把 `slow_ms` 从环境变量读到中间件
- [ ] 动手题二：给 `get_conn` 加 `PRAGMA journal_mode=WAL`

> 想看 `BaseHTTPMiddleware` 与 `@app.middleware` 的差异、`sqlite3.Row` 的坑、`SecretStr` 的三种泄露面、日志 formatter 的 `request_id` 兜底、18 条坑，继续读 [`base.md`](./base.md)。