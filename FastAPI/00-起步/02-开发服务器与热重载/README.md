# 02 开发服务器与热重载

## 一句话结论

`uvicorn` 是 ASGI 服务器，负责「监听端口 + 把 HTTP 翻译成 ASGI 事件」；FastAPI 只是 ASGI 应用。`--reload` 是**开发期**的文件监听重启，`--workers` 是**生产期**的多进程并行，两者语义不同且 `--reload` 会直接忽略 `--workers`。

学完这一章，你能：看懂启动日志的每一行、判断「改了代码不生效」的 7 种原因、说清多进程下哪些设计会失效。

## 最小可运行案例

```python
import os
import time

from fastapi import FastAPI

app = FastAPI()

# 【作用】把进程信息暴露出来，用于观察 reload / workers 的真实行为
STARTED_AT = time.time()
PID = os.getpid()


@app.get("/whoami")
def whoami() -> dict[str, object]:
    return {"pid": PID, "ppid": os.getppid(), "uptime": round(time.time() - STARTED_AT, 2)}
```

完整带注释版本见 `examples/main.py`。

## 怎么跑

```powershell
cd "00-起步\02-开发服务器与热重载\examples"

# 方式一：uvicorn + 热重载（最常用的开发方式）
uv run uvicorn main:app --reload

# 方式二：fastapi-cli（自动寻找 app，默认带 reload）
uv run fastapi dev main.py

# 方式三：代码内启动（不能热重载）
uv run python main.py

# 观察进程
curl http://127.0.0.1:8000/whoami
```

预期启动日志（实测）：

```text
INFO:     Will watch for changes in these directories: ['...\examples']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [98948] using WatchFiles
INFO:     Started server process [29848]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

四行日志的含义：

| 行 | 含义 | 关键信息 |
| --- | --- | --- |
| `Will watch for changes in` | reload 的监控目录 | 默认是当前工作目录 |
| `Uvicorn running on` | 监听地址 | host/port 是否写对 |
| `Started reloader process [...] using WatchFiles` | **父进程**：只负责监控文件，不处理请求 | 这个 PID 不是你的服务进程 |
| `Started server process [...]` | **子进程**：真正处理请求 | `/whoami` 返回的是这个 PID |

## 核心 API 速查

| 参数 | 默认值 | 作用 | 注意 |
| --- | --- | --- | --- |
| `--host` | `127.0.0.1` | 绑定地址 | 容器/局域网要 `0.0.0.0` |
| `--port` | `8000` | 端口 | 被占会 `[Errno 10048]` 退出码 3 |
| `--reload` | 关 | 文件变更自动重启 | 仅开发；会忽略 `--workers` |
| `--reload-dir` | 当前目录 | 指定监控目录 | 只监听该目录，可重复给 |
| `--reload-include` | — | 额外监控的 glob | 如 `*.html` |
| `--reload-exclude` | — | 排除的 glob | 如 `*.log`、`.venv` |
| `--reload-delay` | `0.25` | 轮询间隔（秒） | 大项目调大可减少重启 |
| `--workers` | `1` | 工作进程数 | 生产用；与 reload 互斥（忽略） |
| `--app-dir` | 当前目录 | 从哪个目录找 app | 免 `cd` |
| `--log-level` | `info` | 日志级别 | `trace` 可看 ASGI 细节 |
| `--proxy-headers` | 开 | 信任 `X-Forwarded-*` | 反向代理后必开 |
| `--root-path` | `""` | 反向代理子路径 | 第 54 章 |

| 启动方式 | 热重载 | 多进程 | 适用 |
| --- | --- | --- | --- |
| `uvicorn main:app --reload` | ✅ | ❌ | 开发（推荐） |
| `fastapi dev main.py` | ✅ | ❌ | 开发（更省事） |
| `uvicorn main:app --workers 4` | ❌ | ✅ | 生产 |
| `python main.py` | ❌ | ❌ | 调试单文件 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `--reload --workers 4` 以为能两者兼得 | 实测只打 `WARNING: "workers" flag is ignored when reloading is enabled.`，workers 被**忽略**，仍是单进程 | 开发用 reload，生产用 workers，分两条命令 |
| 在项目根目录跑 `uvicorn main:app`，但 `main.py` 在子目录 | `Could not import module "main"` | `--app-dir src` 或 `cd` 到目录 |
| 8000 被占 | 实测 `ERROR: [Errno 10048] error while attempting to bind on address (...)`，退出码 **3** | 换端口；注意日志里会先出现 `Application startup complete` 才报 bind 错，别被误导 |
| 改代码后日志出现 `Reloading...` 但新代码没生效 | 实测本机 uvicorn 0.54.0 + Windows：PID 未变、响应仍是旧值 | 见 `base.md` 4.4 的 7 项排查 |
| `--reload` 监控了整个项目（含 `.venv`） | 装个包就重启、CPU 飙高 | `--reload-dir app` 或 `--reload-exclude .venv` |
| 生产用 `--reload` | 内存翻倍（父+子）、文件监听占 CPU、重启期间请求失败 | 生产 `--workers` |
| 多进程下用模块级 `dict` 做缓存/限流 | 每个进程各存一份，数据不一致 | 用 Redis/DB，或单进程 + 外部存储 |
| 把 `reloader process` 的 PID 当成服务 PID | 杀错进程、监控采错指标 | 只认 `Started server process` 的那个 |
| `--reload` 在 Docker 里挂了代码卷但不生效 | inotify 事件不跨挂载传播 | 用轮询：`--reload-delay` 或看 `--reload-include` |

## 毕业自查

- [ ] 能说出启动日志四行各自代表什么
- [ ] 能解释 `reloader process` 与 `server process` 的关系
- [ ] 能说出 `--reload` 与 `--workers` 同时给会发生什么（实测：workers 被忽略 + WARNING）
- [ ] 能说出 8000 被占时的报错文本与退出码
- [ ] 能列举「改了代码不生效」的至少 5 种原因
- [ ] 能说出多进程下哪三类代码会失效（内存缓存、全局计数器、内存队列）
- [ ] 动手题一：用 `--workers 2` 启动，请求 `/whoami` 20 次，统计出现几个不同 PID
- [ ] 动手题二：用 `--reload-dir` 把监控范围收窄到 `examples` 以外的一个空目录，确认改代码不再触发重启

> 想看进程模型、reload 机制、参数全表与 39 条坑，继续读 [`base.md`](./base.md)。
