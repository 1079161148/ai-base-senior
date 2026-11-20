# 67 lifespan 生命周期

## 一句话结论

一个 `@asynccontextmanager` 同时管启动和关闭：**`yield` 之前**是启动（可 `await`、可预热），**`yield` 之后**是关闭（放 `finally`）。实测顺序严格是 `startup:begin → startup:end → 请求 → shutdown:begin → shutdown:end`；启动阶段抛异常则**应用根本起不来**（只跑了 `failing:startup`，没有 shutdown）；关闭阶段抛异常则**响应早已正常返回**，异常在 `with` 退出时抛出。`TestClient` 必须用 `with` 才会触发 lifespan，不加 `with` 一条事件都不会跑。

## 最小可运行案例

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # ---- 启动 ----
    app.state.cache = {"warmed": True}
    try:
        yield
    finally:
        # ---- 关闭 ----
        app.state.cache.clear()


app = FastAPI(lifespan=lifespan)


@app.get("/ping")
def ping(request: Request) -> dict:
    return {"warmed": request.app.state.cache.get("warmed", False)}
```

## 怎么跑

```powershell
cd "11-应用结构\67-lifespan 生命周期\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 无 with 不触发 -> 未触发任何事件
[PASS] 进入触发 startup -> startup:begin → startup:end
[PASS] startup 顺序 -> begin → end
[PASS] 资源已预热 -> warmed=True, rows=5
[PASS] uptime 写入 -> 2.5ms
[PASS] 退出触发 shutdown -> shutdown:begin → shutdown:end
[PASS] 完整顺序 -> startup:begin → startup:end → shutdown:begin → shutdown:end
[PASS] 两次运行 -> startup ×2 / shutdown ×2
[PASS] 启动失败 -> 预热失败，服务不该起来
[PASS] 失败无 shutdown -> 只有 startup，没有 shutdown
[PASS] 关闭异常不影响响应 -> 响应 200 已返回（异常发生在退出时）
[PASS] 关闭异常在退出抛出 -> 关闭时炸了
[PASS] state 跨请求 -> 两次请求共享 started_at
[PASS] startup 真 await -> 进入耗时 31ms（含 10ms 预热）

结果：14/14 通过
```

## 核心 API 速查

| 位置 | 执行时机 | 典型用途 |
| --- | --- | --- |
| `yield` 之前 | 应用启动、接受请求前 | 连 DB、预热缓存、读配置 |
| `yield` 之后（`finally`）| 应用关闭 | 关连接、刷缓冲、退订 |
| `app.state.xxx` | 全程 | 存共享资源 |
| `@app.on_event` | 已废弃 | 改用 lifespan |

| 异常位置 | 结果 |
| --- | --- |
| 启动阶段 | 应用起不来，无 shutdown（实测）|
| 关闭阶段 | 响应已发完，退出时抛（实测）|
| 请求处理中 | 正常 500 流程 |

| 实测 | 值 |
| --- | --- |
| 不加 `with` | 事件为空 |
| `with` 进入 | `startup:begin → startup:end` |
| 退出 | `shutdown:begin → shutdown:end` |
| 预热 `await` 10ms | 进入耗时 31ms |
| 两次 `with` | startup ×2 / shutdown ×2 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 关闭代码写在 `yield` 后但不在 `finally` | 异常时泄漏 | `try/finally` |
| `TestClient` 不加 `with` | lifespan 不跑，资源是 None | `with TestClient(app)` |
| 启动阶段做重活 | 服务迟迟不可用 | 轻量预热或后台任务 |
| 在 lifespan 里抛异常当校验 | 服务直接起不来 | 明确这是预期行为 |
| 关闭阶段抛异常 | 日志报错但已无法影响响应 | 尽力清理 + 记日志 |
| 用 `@app.on_event` | DeprecationWarning | `lifespan` |
| 把资源挂在模块全局 | 多 app 冲突 | `app.state` |
| 启动时 `await` 长任务 | 阻塞启动 | `asyncio.create_task` + 关闭时取消 |
| 多 worker 以为只跑一次 | 每个 worker 各跑一次 | 按进程设计 |
| lifespan 里用同步阻塞 IO | 阻塞启动事件循环 | `to_thread` |
| 忘记取消后台任务 | 关闭后仍在跑 | `finally: task.cancel()` |
| 用 `app.state` 存请求级数据 | 串用户数据 | 请求级用依赖 |
| 依赖 `TestClient` 自动跑 lifespan | 不加 `with` 不跑 | 显式 `with` |
| 关闭时删测试库文件 | 下次启动重建 | 视场景而定 |

## 毕业自查

- [ ] 能写出完整 lifespan
- [ ] 能说清 `yield` 前后分别是什么
- [ ] 能解释启动失败为什么不执行 shutdown
- [ ] 能解释关闭异常为什么改不了响应
- [ ] 知道 `TestClient` 必须 `with`
- [ ] 动手题一：把预热改成「从文件读 1 万行」
- [ ] 动手题二：加一个后台心跳任务，关闭时取消

> 想看 ASGI lifespan 协议、`startup`/`shutdown` 消息、多 worker、优雅停机、与 `lifespan_context` 的关系、18 条坑，继续读 [`base.md`](./base.md)。