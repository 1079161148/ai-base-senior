# 76 部署与交付

## 一句话结论

交付四件事：**探针分开**（`/healthz` 只证明活着、**不查依赖**，`/readyz` 查依赖、失败 503）、**进程参数对**（`--workers`、`--proxy-headers`、生产不开 `--reload`）、**容器非 root + `HEALTHCHECK` + 日志到 stdout**、**退出能跑完 lifespan 的 shutdown**。实测：把依赖标记为坏之后 `/healthz` 仍 **200**、`/readyz` 变 **503**——这正是「数据库抖动不该触发全量重启」的关键；`with TestClient` 退出后 `shutdown_done=True`，证明优雅退出路径通。生产形态关掉 `/docs` 与 `/openapi.json` 后业务 `/items` 仍 200。

## 最小可运行案例

```python
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Response, status

STATE: dict[str, Any] = {"ready": False, "db_ok": True}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    STATE["ready"] = False
    await connect()                 # 建连接池
    STATE["ready"] = True
    try:
        yield
    finally:                        # SIGTERM 后必须快速跑完
        STATE["ready"] = False
        STATE["db_ok"] = False


app = FastAPI(lifespan=lifespan, docs_url=None if os.getenv("APP_ENV") == "prod" else "/docs")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """liveness：不查依赖"""
    return {"status": "ok"}


@app.get("/readyz")
def readyz(response: Response) -> dict[str, Any]:
    """readiness：查依赖，失败 503"""
    if not (STATE["ready"] and STATE["db_ok"]):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not ready", "db_ok": STATE["db_ok"]}
    return {"status": "ready", "db_ok": True}
```

## 怎么跑

```powershell
cd "12-测试调试\76-部署与交付\examples"
uv sync
uv run python verify.py
uv run pytest -q
```

预期输出：

```text
[PASS] healthz 200 -> 200 / ok
[PASS] liveness 不查依赖 -> healthz 200 / readyz 503
[PASS] readyz 200 -> ready / db_ok=True
[PASS] readyz 503 -> 503 / db_ok=False
[PASS] 版本头 -> 1.0.0
[PASS] 运行信息 -> env=dev port=8000
[PASS] 优雅退出 -> ready False / shutdown_done True
[PASS] 生产关 docs -> /docs 404
[PASS] 生产关 schema -> /openapi.json 404
[PASS] 生产业务可用 -> 200 / 业务正常
[PASS] 多 worker -> workers=4
[PASS] 无 reload -> CMD 无 --reload
[PASS] 非 root -> USER appuser
[PASS] HEALTHCHECK -> HEALTHCHECK → /healthz
[PASS] 代理头 -> --proxy-headers 已配置
[PASS] .dockerignore -> .env 已排除

结果：16/16 通过
```

`pytest -q` 另外 7 个用例全绿。

## 核心 API 速查

| 探针 | 查依赖 | 失败码 | 作用 |
| --- | --- | --- | --- |
| `/healthz` | ❌ | 无（进程死了才失败）| liveness，决定是否重启 |
| `/readyz` | ✅ | 503 | readiness，决定是否接流量 |

| uvicorn 参数 | 作用 |
| --- | --- |
| `--host 0.0.0.0` | 容器内可访问 |
| `--workers 4` | 多进程 |
| `--proxy-headers` | 信任 `X-Forwarded-*` |
| `--forwarded-allow-ips` | 限定可信代理 |
| `--timeout-keep-alive 5` | 连接复用上限 |
| `--log-level info` | 日志级别 |
| `--reload` | **仅开发** |

| 实测 | 值 |
| --- | --- |
| `/healthz` | 200 `{"status":"ok","version":"1.0.0"}` |
| 依赖坏时 `/healthz` | 仍 200 |
| 依赖坏时 `/readyz` | 503，`db_ok=False` |
| `X-App-Version` | 1.0.0 |
| 退出后 | `ready=False`、`shutdown_done=True` |
| 生产 `/docs` | 404 |
| 生产 `/openapi.json` | 404 |
| 生产 `/items` | 200 |
| Dockerfile `--workers` | 4 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| liveness 查数据库 | DB 抖动 → 全量重启 | liveness 只查进程 |
| readiness 不查依赖 | 流量打到坏实例 | 查关键依赖 |
| 只做一个探针 | 重启与摘流混一起 | 两个都要 |
| 生产开 `--reload` | 性能差、可能双进程 | 只在开发 |
| 容器里跑 root | 逃逸风险 | `USER appuser` |
| 无 `HEALTHCHECK` | 僵死容器不被换 | 加探针 |
| 日志写文件 | 容器销毁即丢 | stdout |
| 不带 `--proxy-headers` | 拿到的 IP 全是代理 | 加上并限 IP |
| 信任意代理 IP | 可伪造 | `--forwarded-allow-ips` 收紧 |
| workers 开太多 | 内存爆 | `2×CPU+1` 以内 |
| workers 配 SQLite | 写锁竞争 | 换库或单 worker |
| shutdown 里做长任务 | 被 SIGKILL | 快速清理或异步 |
| 构建上下文含 `.env` | 密钥进镜像 | `.dockerignore` |
| `COPY . .` 在装依赖前 | 改代码就重装依赖 | 先 COPY 依赖清单 |
| 镜像用 `latest` 基础镜像 | 不可复现 | 固定 digest/版本 |
| 用例没覆盖 503 分支 | 探针形同虚设 | 补依赖故障用例 |
| 探针路径被鉴权挡住 | K8s 探针 401 | 探针排除鉴权 |
| 探针返回 200 但 body 是错误 | 只看状态码漏检 | 同时断 body |

## 毕业自查

- [ ] 能写出两个探针并说明差别
- [ ] 能证明依赖坏时 liveness 不受影响
- [ ] 能写出生产启动命令
- [ ] 能写 Dockerfile（非 root + HEALTHCHECK）
- [ ] 能证明优雅退出执行了 shutdown
- [ ] 动手题一：把 workers 改成从环境变量读
- [ ] 动手题二：给 `/readyz` 加缓存依赖检查（避免每次打 DB）

> 想看 uvicorn 的 worker 模型、SIGTERM 流程、K8s 探针参数、镜像瘦身、18 条坑，继续读 [`base.md`](./base.md)。