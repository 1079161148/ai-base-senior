# 80 从 0 到 1 搭工程化项目 · 完整版（base.md）

> `README.md` 给你 12 块积木的清单与验收输出；本文件讲清「为什么是这个顺序、每块积木的边界在哪、工厂与依赖覆盖为什么会互相打架、架构守卫怎么写成不会误伤的规则」。学完这章，你能在半天内从空目录搭出一个新人能接手的 FastAPI 项目。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0 / pydantic-settings 2.16（本机实测） |
| 前置 | 77–79（业务/生产化/验收）、65（应用结构）、73（依赖覆盖） |
| 覆盖范围 | 目录分层、配置、迁移、事务、契约、仓储、服务、依赖、错误、可观测、架构守卫、交付 |
| 明确不覆盖 | ORM、Alembic 全量、Celery、K8s 编排、CI 平台具体配置 |
| 学完验收 | `verify.py` 12/12 + `pytest` 19 passed + 守卫 0 违规 |

## 0. 怎么用这份文件

**依据约定**：`` `[d]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 工程化到底判什么
2 机制（第 2 节）    → 12 块积木的因果链
3 拆解（第 3 节）    → 每块的文件与关键 API
4 边界（第 4 节）    → 工厂/覆盖、BOM、迁移、守卫误伤
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 目录模板与接手清单
```

## 1. 概念：工程化的四个判据

| 判据 | 反例 | 本章做法 |
| --- | --- | --- |
| 可替换 | 换库要改业务代码 | `db/` + `repositories/` 收口 |
| 可测试 | 业务逻辑里 `from fastapi import ...` | service 只依赖 `AppError` |
| 可演进 | 手工改表结构 | `migrations/*.sql` + 记账表 |
| 可接手 | 新人要问「跑起来要几步」 | `Makefile` 一条命令 |

**「分层」不是为了好看，是为了让「换掉某一层」这件事成本可预测。**

## 2. 机制：12 块积木的因果链

| 顺序 | 积木 | 前置条件 | 加完之后多出来的能力 |
| --- | --- | --- | --- |
| 1 | 骨架 | 无 | 进程能起、探针能通 |
| 2 | 配置 | 1 | 换环境不改代码 |
| 3 | 迁移 | 2（要 db_path） | 表结构可版本化 |
| 4 | 事务 | 3（要有表） | 写操作原子 |
| 5 | 契约 | 无（可与 2 并行） | 输入输出有边界 |
| 6 | 仓储 | 3、4、5 | SQL 可替换 |
| 7 | 服务 | 5、6 | 业务可单测 |
| 8 | 依赖 | 2、4、6、7 | 各层真正连起来 |
| 9 | 错误 | 5、8 | 客户端一套解析 |
| 10 | 路由+中间件 | 8、9 | 对外可用 + 可观测 |
| 11 | 守卫 | 全部 | 结构不会偷偷腐化 |
| 12 | 交付 | 全部 | 新人能接手 |

**关键因果**：3 必须在 4 之前（没有表谈不上事务），6 必须在 7 之前（service 需要 repo 接口），8 必须在 10 之前（端点靠依赖拿到 service）。

## 3. 每块积木拆解

### 3.1 骨架（`app/main.py`）

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    application = FastAPI(title="工程化脚手架", version=settings.version)
    application.dependency_overrides[get_settings] = lambda: settings   # 见 4.1
    return application

app = create_app()
```

| 决策 | 选择 | 代价 |
| --- | --- | --- |
| 工厂 vs 模块级 | 工厂 + 模块级别名 | 多一层缩进，换来可测试 |
| 文档开关 | `docs_url=None if is_prod` | 生产调试要另开通道 |

### 3.2 配置（`core/config.py`）

| 变量 | 类型 | 校验 |
| --- | --- | --- |
| `APP_ENV` | `Literal[dev/test/prod]` | 非法值启动即失败 |
| `APP_DB_PATH` | `str` | — |
| `APP_TOKEN` | `SecretStr` | `repr` 掩码 |
| `APP_PAGE_SIZE_MAX` | `int` | `ge=1, le=1000` |
| `APP_LOG_LEVEL` | `Literal` 四档 | — |
| `APP_SLOW_MS` | `int` | `ge=1` |

实测 `repr(settings)` 与 `model_dump` 都不含明文令牌。

### 3.3 迁移（`db/migrate.py`）

30 行的迁移器，核心三句：

```python
conn.execute(TRACKING_TABLE)                                  # 建记账表
done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
for path in sorted(MIGRATIONS_DIR.glob("*.sql")):             # 文件名即版本序
    if path.stem in done: continue
    conn.executescript(path.read_text(encoding="utf-8"))
```

实测：首次 `['0001_init','0002_add_pinned']`，二次 `[]`，记账 2 条。

| 与 Alembic 的差异 | 本章 | Alembic |
| --- | --- | --- |
| 版本发现 | 文件名排序 | revision graph |
| 回滚 | 不支持（示例够用） | `downgrade()` |
| 自动生成 | 不支持 | `--autogenerate` |

### 3.4 事务（`db/session.py`）

```python
try:
    yield conn
    conn.commit()
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
```

实测：正常结束 → 1 行；`generator.throw(RuntimeError)` → 回滚后仍 1 行。

**注意**：`GeneratorExit` 不是 `Exception` 子类，生成器被 `close()` 时不会触发 rollback —— 这是「依赖没跑完」的场景，不应吞数据，靠连接关闭时 SQLite 隐式回滚兜底。

### 3.5 契约（`schemas/note.py`）

| 模型 | 用途 | 字段 |
| --- | --- | --- |
| `NoteCreate` | 入参 | `title`、`body` |
| `NoteUpdate` | 部分更新 | 全可选 |
| `Note` | 出参 | `id/title/body/pinned/created_at` |
| `Page[T]` | 分页信封 | `items/total/page/size/pages` |

守卫禁止 schemas import 任何内部层 —— 契约不依赖实现。

### 3.6 仓储（`repositories/note_repo.py`）

| 方法 | SQL 要点 |
| --- | --- |
| `create` | `lastrowid` + 回查 |
| `exists_title` | 支持 `exclude_id`，更新时排除自己 |
| `list` | `WHERE` 白名单拼接 + `?` 绑定；`ORDER BY pinned DESC, id ASC` |
| `update` | 字段名来自固定白名单，值全绑定 |

实测：`exists_title("仓储")` True，`exclude_id=自己` False。

### 3.7 服务（`services/note_service.py`）

| 方法 | 业务规则 |
| --- | --- |
| `create` | 标题唯一 → `DuplicateTitle`(409) |
| `get` | 不存在 → `NotFound`(404) |
| `update` | 改名时检查冲突（排除自己） |
| `toggle_pin` | 读当前值再取反，端点不需要知道状态 |
| `delete` | 不存在 → 404 |

**这一层是唯一该写 `if` 的地方**。端点里出现业务判断就是跑错层了。

### 3.8 依赖（`api/deps.py`）

```text
get_settings
  ├── get_conn ──→ get_repo ──→ get_service
  └── get_current_user
pagination（settings + query）
```

实测：`create_app(settings)` 后依赖树拿到的是传入的 settings（前提是做了 4.1 的覆盖）。

### 3.9 错误（`core/exceptions.py` + `core/errors.py`）

两层分离是关键：

| 层 | 文件 | 允许 import | 谁抛 |
| --- | --- | --- | --- |
| 领域异常 | `core/exceptions.py` | 纯 Python | service |
| HTTP 翻译 | `core/errors.py` | fastapi | 框架 |

四种错误（404/409/422/500）实测同一信封、同一 `error` 顶层键。

### 3.10 路由与中间件（`api/v1/*`、`core/middleware.py`）

| 端点 | 方法 | 鉴权 |
| --- | --- | --- |
| `/api/v1/notes` | GET / POST | 读公开、写要令牌 |
| `/api/v1/notes/{id}` | GET / PATCH / DELETE | 读公开、写要令牌 |
| `/api/v1/notes/{id}/pin` | POST | 要令牌 |
| `/healthz` | GET | 公开 |

中间件给三个头：`X-Request-ID`、`X-Elapsed-Ms`、`X-App-Version`，并打一行日志。

**注意**：`add_exception_handler(Exception, ...)` 由 `ServerErrorMiddleware` 处理，它在用户中间件**外层**，所以 500 响应拿不到中间件加的头。要在 500 上也带头，得在中间件里直接构造响应。

### 3.11 架构守卫（`scripts/arch_guard.py`）

`ast` 解析每个文件的 `Import`/`ImportFrom`，对比 `FORBIDDEN` 表。实测 22 个源文件 0 违规。

为什么不用 grep：`"app.api"` 可能出现在注释、字符串里；`ast` 只看真实 import。

### 3.12 交付（`Makefile`、`Dockerfile`、`scripts/seed.py`）

| 交付物 | 关键点 |
| --- | --- |
| `Makefile` | 6 个目标：install/run/test/verify/migrate/seed |
| `Dockerfile` | 依赖层先于代码层；非 root；HEALTHCHECK 打 `/healthz`；`--workers 2`；无热重载 |
| `.env.example` | 列出全部 `APP_*`，不含真实密钥 |
| `scripts/seed.py` | 走 service 而非裸 INSERT，规则不会被绕过 |

## 4. 边界条件

### 4.1 工厂传参与依赖覆盖的冲突（实测）

`create_app(settings)` 只影响「中间件/版本/lifespan」，但端点里的 `Depends(get_settings)` 走的是模块级 `@lru_cache` 单例。

实测症状：测试传 `token="test-token"`，接口仍返回 **401**；查库也落在默认 `app.db` 上，导致 `notes` 表不存在 → **500**。

修法：

```python
application.dependency_overrides[get_settings] = lambda: settings
```

这条不是「测试技巧」，而是**工厂契约的一部分**：工厂既然允许传配置，就必须让配置贯穿依赖树。

### 4.2 BOM 与 `ast`

`Set-Content -Encoding UTF8`（PowerShell 5）会写入 BOM。`import` 能接受，`ast.parse` 不能：

```text
SyntaxError: invalid non-printable character U+FEFF
```

修法：写入用无 BOM UTF-8；读取用 `encoding="utf-8-sig"`（守卫里已做，双重保险）。

### 4.3 迁移的三种失败

| 场景 | 表现 | 处理 |
| --- | --- | --- |
| 重复执行 | `duplicate column name` | 记账表跳过 |
| 中途失败 | 部分 DDL 已生效 | SQLite DDL 自动提交，需手工修复；生产建议事务型库 |
| 乱序添加 | 老库缺新表 | 只允许追加，不改历史文件 |

### 4.4 守卫规则会误伤吗

| 写法 | 是否违规 | 说明 |
| --- | --- | --- |
| `from app.api import deps` in `services/` | 违规 | 正确 |
| `from app.apix import x` in `services/` | 不违规 | 前缀带 `.` 精确匹配 |
| `# 参考 app.api 的做法` in `services/` | 不违规 | `ast` 不看注释 |
| `import fastapi` in `core/errors.py` | 不违规 | core 允许 fastapi |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 工厂传参但依赖仍用单例 | 401/500 且库不对 | 覆盖 `get_settings` | 实测 |
| 直接 `app = FastAPI()` | 无法多环境 | `create_app(settings)` | 实测 |
| 手工 `ALTER TABLE` | CI 建库失败 | 迁移文件 | 实测 |
| 迁移不记账 | 二次启动报错 | `schema_migrations` | 实测 |
| 历史迁移文件被修改 | 老库与新库结构不一致 | 只追加新文件 | 实测 |
| 端点手动 `commit` | 异常留脏数据 | 依赖里统一 | 实测 |
| 异常吞掉不 `raise` | 错误变 200 | 回滚后继续抛 | 实测 |
| service import `HTTPException` | 业务绑死框架 | 抛 `AppError` | 实测 |
| repo import `Query` | 换协议要改数据层 | 只返回 dict | 实测 |
| schemas import `app.db` | 契约依赖实现 | 守卫拦截 | 实测 |
| 业务 `if` 写在端点 | 无法单测 | 下沉到 service | 实测 |
| 错误处理器只注册一个 | 两种信封 | 四类全注册 | 实测 |
| 500 想靠中间件加头 | 头丢失 | 在中间件内构造响应 | 实测 |
| `__init__.py` 带 BOM | `ast.parse` 失败 | 无 BOM 写入 | 实测 |
| 守卫用 grep | 注释/字符串误判 | `ast` 解析 | 实测 |
| 守卫只在 `make` 里跑 | 有人绕过 | 做成 pytest 用例 | 实测 |
| Dockerfile 带热重载 | 生产 CPU/内存异常 | 只留 `--workers` | 实测 |
| `.env` 提交进仓库 | 密钥泄露 | 只提交 `.env.example` | 实测 |
| 迁移里删表再重建 | 丢索引/外键/触发器 | 优先 `ALTER TABLE` | 实测 |

## 6. 最佳实践与编码建议

### 6.1 目录模板（可直接复制）

```text
app/
├── main.py                 # 装配：create_app + lifespan
├── core/                   # 横切关注点
│   ├── config.py           #   配置
│   ├── exceptions.py       #   领域异常（纯 Python）
│   ├── errors.py           #   HTTP 错误契约
│   ├── logging.py          #   日志
│   └── middleware.py       #   请求 ID / 耗时
├── db/
│   ├── session.py          #   连接 + 事务
│   ├── migrate.py          #   迁移器
│   └── migrations/*.sql    #   只追加
├── schemas/                # 契约（只依赖 pydantic）
├── repositories/           # SQL（只依赖 sqlite3）
├── services/               # 业务规则（禁 fastapi / sqlite3）
└── api/
    ├── deps.py             # 依赖装配
    └── v1/{router,notes}.py
```

### 6.2 新增一个业务模块的 5 个动作

```text
1 schemas/xxx.py            定义 Create/Update/Out/Page
2 repositories/xxx_repo.py  写 SQL（全 ? 绑定）
3 services/xxx_service.py   写业务规则（抛 AppError 子类）
4 api/v1/xxx.py             写端点（< 10 行/个）
5 api/v1/router.py          挂一行 include_router
```

再跑 `verify.py` 与 `arch_guard.py`，两个都绿才算加完。

### 6.3 接手清单（贴进 README）

| 问题 | 命令 |
| --- | --- |
| 怎么装依赖 | `make install` |
| 怎么起服务 | `make run` |
| 怎么建表 | 启动时自动 `migrate()`，或 `make migrate` |
| 怎么灌数据 | `make seed` |
| 怎么验完整性 | `make verify && make test` |
| 怎么发布 | 构建镜像，`CMD` 已含 `--workers` |

### 6.4 何时该放弃这套结构

| 场景 | 更合适的选择 |
| --- | --- |
| 只有 3 个端点 | 单文件 + 无分层 |
| 需要事务型库、复杂查询 | SQLAlchemy / Alembic / 迁移图 |
| 多服务共享模型 | 独立包 + 版本化契约 |
| 团队 > 5 人 | 按领域拆服务，而非按技术分层 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[d1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/events/ | lifespan |
| `[d2]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/testing-dependencies/ | `dependency_overrides` |
| `[d3]` | 文档 | https://docs.python.org/3/library/ast.html | `ast.parse` |
| `[d4]` | 方法论 | https://12factor.net/zh_cn/ | 配置外置、无状态 |

> **核对状态**：`[d1]`–`[d4]` 为文档/方法论链接，**本次未逐页直连复核**；12 块积木全部为本机实测（12/12），`pytest -q` 19 passed，架构守卫 22 个源文件 0 违规，迁移首次 2 个/二次 0 个，事务提交 1 行/回滚后仍 1 行。真实 `docker build`、多 worker 下的 SQLite 写竞争、Postgres 替换、CI 平台配置**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 工程化的四个判据
- [ ] 12 块积木的因果顺序（为什么 3 在 4 前、6 在 7 前）
- [ ] 工厂与依赖覆盖为什么会打架
- [ ] 守卫为什么用 `ast` 而不是 grep
- [ ] 什么场景该放弃这套结构

**能写出（代码层）**：

- [ ] `create_app(settings)` 工厂 + `dependency_overrides`
- [ ] 30 行迁移器（记账 + 跳过）
- [ ] 事务生成器依赖（commit/rollback/close）
- [ ] `FORBIDDEN` 表 + `ast` 扫描
- [ ] Makefile 六个目标

**能判断（避坑层）**：

- [ ] 看到测试 401 → 先查 `get_settings` 覆盖
- [ ] 看到 `duplicate column` → 查记账表
- [ ] 看到 `U+FEFF` → 查文件 BOM
- [ ] 看到业务里 import `HTTPException` → 该抛 `AppError`
- [ ] 看到守卫红 → 先看是真违规还是前缀误伤

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 12/12
- [ ] `uv run pytest -q` 输出 19 passed
- [ ] `uv run python scripts/arch_guard.py` 输出「分层依赖全部合法」
- [ ] 故意在 `services/` 里加 `from fastapi import Depends`，确认守卫变红，再删掉

## 9. 与整套教程的衔接

| 本章的积木 | 出自哪一章 | 本章只做了一件事 |
| --- | --- | --- |
| 配置 | 66 | 挪进 `core/config.py` 并接入工厂 |
| 迁移 | 57、76 | 抽成 30 行可复用脚本 |
| 事务 | 57、78 | 绑到生成器依赖上 |
| 契约 | 02、03 | 按层拆到 `schemas/` |
| 依赖 | 06、73 | 串成 `conn → repo → service` |
| 错误 | 05、09 | 领域异常与 HTTP 翻译分离 |
| 中间件/日志 | 08、75 | 三个头 + 一行日志 |
| 测试 | 71–74 | 单元/接口/架构三层 |
| 交付 | 76 | Makefile + Dockerfile + seed |

**下一步建议**：

1. 把这套骨架复制到一个真实需求上，先写 `schemas/`，再写 `migrations/`，最后写 `services/`。
2. 每加一个模块跑一次 `verify.py` 与 `arch_guard.py`——**验收脚本是唯一可信的完成标准**。
3. 需要事务型库时把 `db/` 与 `repositories/` 换掉，守卫会告诉你有没有漏改的地方。