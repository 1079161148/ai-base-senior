# 80 从 0 到 1 搭工程化项目

## 一句话结论

工程化项目不是「一口气写完再分层」，而是**按依赖方向逐块加积木，每加一块都能跑通验收**。本章用 12 块积木把 `app/` 搭出来：骨架 → 配置 → 迁移 → 事务 → 契约 → 仓储 → 服务 → 依赖 → 错误 → 路由中间件 → 架构守卫 → 交付物，实测 12/12，其中**积木 11 的架构守卫**扫描 22 个源文件，确认依赖只允许单向流动（`api → services → repositories → db`），这是唯一能防止半年后目录还在、分层已经乱掉的机制。

## 最小可运行案例

第一块积木：一个能返回 200 的工厂函数。**先让它跑起来，再谈结构**。

```python
# app/main.py（积木 1 的最小版）
from fastapi import FastAPI

from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    application = FastAPI(title="工程化脚手架", version=settings.version)

    @application.get("/healthz", tags=["诊断"], summary="存活探针")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": settings.version}

    return application


app = create_app()   # 只留给 uvicorn app.main:app 用
```

```bash
uv run uvicorn app.main:app --reload
# curl http://127.0.0.1:8000/healthz → {"status":"ok","version":"0.1.0"}
```

**为什么先写工厂而不是直接 `app = FastAPI()`**：工厂让「同一份代码 + 不同配置」成为可能。测试传临时库、生产读环境变量，都靠这一个入口。代价是所有 `Depends` 必须显式注入 settings——漏了就会出现「测试传了配置但没生效」（本章实测踩过，见坑表第 1 条）。

## 怎么跑

```powershell
cd "14-工程化实战\80-从0到1搭工程化项目\examples"
uv sync
uv run python verify.py        # 12 块积木
uv run pytest -q               # 19 个用例
uv run python scripts/arch_guard.py   # 只跑架构守卫

# 手动起服务
Copy-Item .env.example .env
uv run uvicorn app.main:app --reload
```

预期输出：

```text
[PASS] 积木 1 骨架 -> 27 个文件 / 6 层：api,core,db,repositories,schemas,services
[PASS] 积木 2 配置 -> env=test / db=verify.db / 密钥已掩码
[PASS] 积木 3 迁移 -> 首次 2 个 / 二次 0 个 / 记录 2 条
[PASS] 积木 4 增量迁移 -> 列：id,title,body,created_at,pinned
[PASS] 积木 5 事务 -> 提交 1 条 / 回滚后仍 1 条
[PASS] 积木 6 仓储 -> create/get/list/exists/delete 全通
[PASS] 积木 7 服务 -> 409 / 404 / toggle_pin 全通
[PASS] 积木 8 接口 -> 201+Location / 分页 / 详情 / 部分更新 / 204
[PASS] 积木 9 错误契约 -> 404 / 409 / 422 / 500 同一信封
[PASS] 积木 10 可观测 -> 请求 ID / 版本头 / 耗时头 / 一行日志
[PASS] 积木 11 架构守卫 -> 22 个源文件依赖方向合法
[PASS] 积木 12 交付物 -> Makefile 6 目标 / 镜像非 root+探针 / .env.example 齐全

结果：12/12 通过
```

## 12 块积木

**搭建顺序即依赖顺序**：每一块只允许依赖它上面已经存在的块。

| # | 积木 | 解决什么 | 新增文件 | 怎么验 |
| --- | --- | --- | --- | --- |
| 1 | 骨架 | 先跑起来 | `app/main.py`、`__init__.py` | `/healthz` 200 |
| 2 | 配置 | 没有硬编码 | `core/config.py`、`.env.example` | 换 `APP_*` 生效 |
| 3 | 迁移 | 表结构可演进 | `db/migrate.py`、`migrations/*.sql` | 跑两次，第二次 0 个 |
| 4 | 事务 | 写一半失败不留脏数据 | `db/session.py` | throw 后行数不变 |
| 5 | 契约 | 请求/响应边界 | `schemas/note.py` | 422 能命中 `body.title` |
| 6 | 仓储 | SQL 集中，可换库 | `repositories/note_repo.py` | 不启 HTTP 也能增删查 |
| 7 | 服务 | 业务规则独立可单测 | `services/note_service.py` | 重复标题抛 409 |
| 8 | 依赖 | 把各层连起来 | `api/deps.py` | 覆盖依赖能换实现 |
| 9 | 错误 | 客户端只需一套解析 | `core/exceptions.py`、`core/errors.py` | 四种错误同一信封 |
| 10 | 路由+中间件 | 暴露端点 + 可观测 | `api/v1/*`、`core/middleware.py` | 请求 ID + 一行日志 |
| 11 | 架构守卫 | 防止分层腐化 | `scripts/arch_guard.py`、`tests/test_architecture.py` | 违规即红 |
| 12 | 交付 | 新人一条命令上手 | `Makefile`、`Dockerfile`、`scripts/seed.py` | 6 个 make 目标 |

### 依赖方向（唯一允许的形状）

```text
        api/            ← 可以 import 下面所有层
         ↓
      services/         ← 只能 import repositories + core.exceptions
         ↓
   repositories/        ← 只能 import sqlite3 + 标准库
         ↓
        db/             ← 只能 import core.config

  core/ 是横切：config/logging/errors/middleware/exceptions，
  它不允许反向依赖 api/services/repositories
```

守卫规则写在一处，测试与验收共用：

```python
# scripts/arch_guard.py
FORBIDDEN = {
    "schemas": ("fastapi", "starlette", "sqlite3", "app.api", "app.services",
                "app.repositories", "app.db", "app.core"),
    "repositories": ("fastapi", "starlette", "app.api", "app.services"),
    "services": ("fastapi", "starlette", "sqlite3", "app.api"),
    "core": ("app.api", "app.services", "app.repositories", "app.db"),
    "db": ("app.api", "app.services", "app.repositories"),
}
```

### 三个决定成败的细节

| 细节 | 位置 | 不这么做的后果 |
| --- | --- | --- |
| 工厂里覆盖 `get_settings` | `app/main.py` | 测试传的配置不生效（实测踩过） |
| 迁移用 `schema_migrations` 记账 | `db/migrate.py` | 重复执行报「列已存在」 |
| 事务放在生成器依赖里 | `db/session.py` | 端点忘了 `commit`，数据时有时无 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `create_app(settings)` 但依赖仍 `Depends(get_settings)` | 测试传的库/令牌不生效，接口 401 | 工厂里 `dependency_overrides[get_settings] = lambda: settings` |
| 手工改表结构 | 本地能跑、CI 建库失败 | 只通过 `migrations/*.sql` 改 |
| 迁移不记账 | 第二次启动报「duplicate column」 | `schema_migrations` + 跳过已应用 |
| 端点在 `try` 里手动 `commit` | 异常路径留脏数据 | 依赖里统一 commit/rollback |
| service 里 `from fastapi import HTTPException` | 业务绑死框架，单测要起 app | 抛 `AppError`，HTTP 层翻译 |
| repo 里 `from fastapi import Query` | 换库/换协议要动业务 | 只返回 `dict` |
| `__init__.py` 带 BOM | `ast.parse` 报 `U+FEFF` | 写文件用 UTF-8 无 BOM，读用 `utf-8-sig` |
| 只在 `make test` 里跑架构检查 | 有人绕过 make 直接 pytest | 把守卫做成 pytest 用例 |
| Dockerfile 里 `--reload` | 生产内存翻倍、文件监听占用 CPU | 只留 `--workers` |

## 毕业自查

- [ ] 12 块积木按顺序能复述「为什么现在加这块」
- [ ] 能画出依赖方向图并解释每条禁止边
- [ ] 能只改 `.env` 把服务指向另一个库
- [ ] 能新增 `0003_*.sql` 并让 `migrate()` 幂等应用
- [ ] 能证明「service 不 import fastapi」是原子测试
- [ ] 动手题一：加 `POST /notes/{id}/pin` 的「置顶数上限 3」业务规则（只改 service）
- [ ] 动手题二：把 SQLite 换成 Postgres，只改 `db/` 与 `repositories/`，验证守卫仍绿

> 想看每块积木的「为什么在这个位置」「工厂与依赖覆盖的因果」「迁移器 30 行怎么写」「架构守卫怎么防误伤」，以及 18 条坑，继续读 [`base.md`](./base.md)。