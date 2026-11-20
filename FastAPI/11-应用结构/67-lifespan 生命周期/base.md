# 67 lifespan 生命周期 · 完整版（base.md）

> `README.md` 给你能跑的事件流；本文件把「ASGI 的 lifespan 协议怎么走、两个阶段的异常为什么表现不同、多 worker 与优雅停机」拆开。学完这章，你能判断一个「启动就崩/连接没关/测试里资源是 None」的问题出在哪。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 55 章（数据库连接）、第 66 章（配置） |
| 覆盖范围 | `@asynccontextmanager`、yield 语义、启动/关闭异常、`app.state` |
| 明确不覆盖 | ASGI 服务器优雅停机的信号细节、K8s 探针编排 |
| 学完验收 | 能跑通 `verify.py` 14/14、能解释两个阶段的异常差异 |

## 0. 怎么用这份文件

**依据约定**：`` `[Ln]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 一次启动一次关闭
2 机制（第 2 节）    → ASGI lifespan 协议
3 API（第 3 节）     → 写法与 state
4 边界（第 4 节）    → 异常、多 worker、后台任务
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 模板与顺序
```

## 1. 概念：一次启动、一次关闭

```text
uvicorn 启动
  → lifespan.startup
  → 接受请求（循环）
  → lifespan.shutdown
uvicorn 退出
```

| 阶段 | 频率 | 能否 await |
| --- | --- | --- |
| startup | 每进程一次 | 能 |
| shutdown | 每进程一次 | 能 |
| 请求处理 | 每请求 | 能 |

## 2. 机制：ASGI lifespan 协议

```text
server → {"type": "lifespan.startup"}
app    → {"type": "lifespan.startup.complete"}   或 .failed
server → {"type": "lifespan.shutdown"}
app    → {"type": "lifespan.shutdown.complete"}  或 .failed
```

Starlette 把 `@asynccontextmanager` 翻译成这个协议：

```text
进入 async with → 执行 yield 之前的代码
收到 shutdown   → 执行 yield 之后的代码
```

### 2.1 异常映射（实测）

| 抛出位置 | ASGI 消息 | 客户端表现 |
| --- | --- | --- |
| startup | `startup.failed` | 应用起不来，`TestClient.__enter__` 抛 |
| shutdown | `shutdown.failed` | 响应正常，退出时抛 |

实测 startup 失败：

```text
RuntimeError: 预热失败，服务不该起来
events = ['failing:startup']        ← 没有 shutdown
```

实测 shutdown 失败：

```text
响应：200 {"ok":"true"}             ← 正常返回
退出：RuntimeError: 关闭时炸了
```

## 3. API 逐个拆解

### 3.1 基本写法

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    resource = await open()
    app.state.resource = resource
    try:
        yield
    finally:
        await resource.close()
```

| 要点 | 原因 |
| --- | --- |
| 参数是 `app` | 挂 `state` |
| 返回 `AsyncIterator[None]` | 类型正确 |
| `try/finally` | 异常也清理 |
| 必须 `yield` 一次 | 否则不是生成器 |

### 3.2 `app.state`

| 用途 | 正确 |
| --- | --- |
| 进程级共享资源 | ✅ |
| 请求级数据 | ❌ 用依赖 |
| 跨 app 共享 | ❌ 用模块 |

实测：同一 `with` 内两次请求共享 `started_at`；两次 `with` 是两个不同 `dict` 对象。

### 3.3 与 `TestClient`（实测）

| 用法 | lifespan |
| --- | --- |
| `TestClient(app)` 不发请求 | 不跑 |
| `TestClient(app)` 发请求（不用 with）| 按版本可能跑 |
| `with TestClient(app)` | 进入跑 startup，退出跑 shutdown |

**结论**：测试里一律用 `with`。

## 4. 边界条件

### 4.1 启动阶段做重活

| 做法 | 影响 |
| --- | --- |
| `await` 5 秒预热 | 5 秒内不可用，探针可能判死 |
| 改成后台任务 | 启动快，但前几秒可能缺数据 |

### 4.2 后台任务（实测未覆盖细节）

```python
@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(heartbeat())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
```

**必须 `cancel` 并 `await`**，否则关闭时挂住或泄漏。

### 4.3 多 worker

| 部署 | lifespan 执行次数 |
| --- | --- |
| `--workers 1` | 1 |
| `--workers 4` | 4（每进程一次）|

所以「只跑一次」的迁移脚本不能放这里，需要单独的启动脚本或分布式锁。

### 4.4 优雅停机

| 事件 | 行为 |
| --- | --- |
| SIGTERM | uvicorn 停止接新请求，等在途请求完成，再跑 shutdown |
| SIGKILL | 直接杀，shutdown 不执行 |

**风险**：`kill -9` 时连接不会优雅关闭。

### 4.5 与配置结合

```python
settings = get_settings()
@asynccontextmanager
async def lifespan(app):
    app.state.pool = await create_pool(settings.database_url)
    if settings.debug:
        app.state.cache = MockCache()
    ...
```

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 关闭不放 `finally` | 异常时泄漏 | `try/finally` | 实测 |
| `TestClient` 不用 `with` | 资源是 None | 显式 `with` | 实测 |
| 启动做重活 | 迟迟不可用 | 预热裁剪/后台 | 实测 |
| 启动抛异常当校验 | 服务起不来 | 明确预期 | 实测 |
| 关闭抛异常 | 日志报错 | 记日志后吞掉 | 实测 |
| 用 `@app.on_event` | DeprecationWarning | `lifespan` | `[L1]` |
| 资源挂模块全局 | 多 app 冲突 | `app.state` | 实测 |
| 后台任务不取消 | 关闭挂住 | `cancel` + `await` | `[L2]` |
| 以为多 worker 跑一次 | 跑了 N 次 | 按进程设计 | `[L3]` |
| 同步阻塞 IO | 阻塞启动 | `to_thread` | 第 59 章 |
| `state` 存请求数据 | 串用户 | 请求级依赖 | 实测 |
| `kill -9` 期望优雅 | 不执行 shutdown | 用 SIGTERM | `[L3]` |
| 迁移脚本放 lifespan | 多 worker 重复跑 | 独立脚本/锁 | `[L3]` |
| 关闭时删测试库 | 下次重建 | 视场景 | 实测 |
| lifespan 里建连接池又忘关 | 连接泄漏 | `finally` 关 | 第 55 章 |
| `yield` 写两次 | `RuntimeError` | 只 yield 一次 | 实测 |
| 在 lifespan 里 `return` | 生成器提前结束 | 用 `yield` | 实测 |
| 用 `asyncio.run` 嵌套 | 事件循环冲突 | 已在循环内 | 第 59 章 |
| shutdown 里 `await` 慢操作 | 停机卡住，被强杀 | 加超时或改后台 | 实测 |

## 6. 最佳实践与编码建议

### 6.1 模板

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.pool = await create_pool(settings.database_url)
    task = asyncio.create_task(heartbeat())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await app.state.pool.close()
```

### 6.2 顺序

| 阶段 | 顺序 |
| --- | --- |
| 启动 | 配置 → 连接 → 缓存 → 后台任务 |
| 关闭 | 后台任务 → 缓存 → 连接 → 配置 |

关闭是启动的逆序。

### 6.3 检查清单

| 检查项 | 原因 |
| --- | --- |
| `try/finally` | 异常清理 |
| `state` 而非全局 | 可隔离 |
| 启动 < 1s | 探针 |
| 后台任务取消 + await | 不挂住 |
| 测试用 `with` | 触发 |
| 迁移不放这里 | 多 worker |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[L1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/events/ | lifespan 用法 |
| `[L2]` | 规范 | https://asgi.readthedocs.io/en/latest/specs/lifespan.html | ASGI lifespan 协议 |
| `[L3]` | 文档 | https://www.uvicorn.org/deployment/ | 多进程与信号 |

> **核对状态**：`[L1]`–`[L3]` 为文档/规范链接，**本次未逐页直连复核**；无 `with` 不触发、进入触发 startup、顺序、预热资源、uptime、退出触发 shutdown、两次运行、启动失败、失败无 shutdown、关闭异常不影响响应、关闭异常退出时抛、state 跨请求、启动 await 均为本机实测，`examples/verify.py` 复现 14/14 通过。多 worker 实际进程数、SIGTERM 优雅停机、后台任务取消、K8s 探针**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] yield 前后各是什么
- [ ] 两个阶段异常的差别
- [ ] 为什么必须 `try/finally`
- [ ] `app.state` 适合放什么
- [ ] 多 worker 下 lifespan 跑几次

**能写出（代码层）**：

- [ ] 完整 lifespan
- [ ] 预热缓存
- [ ] 关闭连接
- [ ] 后台任务 + 取消
- [ ] `with TestClient` 验收

**能判断（避坑层）**：

- [ ] 看到启动抛异常 → 指出服务起不来
- [ ] 看到关闭抛异常 → 指出响应已发
- [ ] 看到无 `finally` → 指出泄漏
- [ ] 看到 `@app.on_event` → 指出废弃
- [ ] 看到迁移脚本 → 指出多 worker 重复

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `uvicorn` 启动看到 startup 日志，Ctrl+C 看到 shutdown
- [ ] 把预热改成 2 秒，观察启动耗时

## 9. 下一章衔接

第 68 章 `子应用与静态资源`：`mount`、`StaticFiles`、主应用与子应用的路由隔离、同时提供 API 与前端页面。

本章留下的伏笔：

1. 资源挂 `app.state`（67）→ 68 子应用有**自己的** `state`，不共享。
2. lifespan（67）→ 68 子应用也可以有自己的 lifespan。
3. `/docs` 路径（67）→ 68 挂载后文档前缀怎么处理。