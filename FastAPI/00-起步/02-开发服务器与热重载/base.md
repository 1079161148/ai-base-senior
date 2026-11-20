# 02 开发服务器与热重载 · 完整版（base.md）

> `README.md` 教你三种启动方式；本文件把「uvicorn 是什么、进程模型怎么分层、reload 到底监控什么、workers 为什么会吃掉你的内存缓存」逐条展开。学完这章，你要能从启动日志一眼判断「服务是不是单进程、有没有开 reload、绑没绑对地址」。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12.8 / FastAPI 0.146.0 / Uvicorn 0.54.0 / WatchFiles（uvicorn[standard] 自带） |
| 前置 | 第 01 章（app 是什么、怎么注册路由） |
| 覆盖范围 | ASGI 服务器职责、三种进程形态、启动日志、参数全表、reload 机制与实测、workers 与状态不共享、端口与绑定、优雅退出 |
| 明确不覆盖 | 反向代理与 `root_path`（54）、容器化部署（76）、进程管理工具（systemd/supervisor） |
| 学完验收 | 能跑通 `verify.py` 6/6、能用 `--workers 2` 观察 2 个 PID、能解释 reload 不生效的 7 种原因 |

## 0. 怎么用这份文件

**依据约定**：`` `[Sn]` `` 指向第 7 节链接；标「实测」的是本机 Uvicorn 0.54.0 / Windows 11 的真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）      → ASGI 服务器与 ASGI 应用是两回事
2 机制（第 2 节）      → 三种进程形态 + reload 的内部动作（重点）
3 参数（第 3 节）      → 每个命令行参数的作用与默认值
4 边界（第 4 节）      → 端口占用、reload 失效、多进程状态、信号
5 注意事项（第 5 节）  → 39 条错误对照
6 最佳实践（第 6 节）  → 命令与脚本约定
```

**与 README 的分工**：README 给你能抄的命令，本文件解释这些命令为什么这么写。

## 1. 概念：服务器是服务器，应用是应用

| 角色 | 例子 | 职责 | 依据 |
| --- | --- | --- | --- |
| ASGI 服务器 | Uvicorn、Hypercorn | 监听端口、解析 HTTP、把请求翻译成 ASGI 事件、把响应写回 socket | `[S1]` `[S2]` |
| ASGI 应用 | 你的 `app = FastAPI()` | 收 `scope/receive/send`，决定返回什么 | `[S1]` |
| ASGI 规范 | PEP 3333 的异步后继 | 定义两者的接口契约 | `[S2]` |

```text
浏览器 ──HTTP──> Uvicorn ──ASGI(scope, receive, send)──> FastAPI app ──> 你的 handler
                    ↑                                        │
                    └──────────── 响应序列化 ←───────────────┘
```

| 关键事实 | 说明 | 依据 |
| --- | --- | --- |
| FastAPI **不能**自己监听端口 | 必须有服务器来跑 | `[S1]` |
| `main:app` 是「导入路径」 | `main` 是模块名、`app` 是模块里的变量名 | `[S2]` |
| 服务器崩溃与应用 bug 是两层问题 | 500 是应用层，端口不通是服务器层 | `[S1]` |

> 注意：这解释了为什么「把 `app` 写在函数里会报 `Could not import module`」——服务器是**导入模块**去找变量，而不是执行你的脚本。`[S2]`

## 2. 机制：三种进程形态

### 2.1 形态一：单进程（`uvicorn main:app`）

```text
[进程 A] 监听端口 + 处理所有请求
```

日志（实测）：

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started server process [77268]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

| 特征 | 说明 |
| --- | --- |
| 只有 1 个 PID | 内存状态唯一、无并发隔离 |
| 崩溃即全站不可用 | 无自动重启 |
| 适合开发与低流量 | 生产需配合进程管理器或 `--workers` |

### 2.2 形态二：reload（`uvicorn main:app --reload`）

```text
[父进程 reloader]  只监控文件，不处理请求
      │ fork/spawn
      └──> [子进程 server] 处理所有请求
```

日志（实测）：

```text
INFO:     Will watch for changes in these directories: ['...\examples']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [98948] using WatchFiles
INFO:     Started server process [29848]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| reload 由 **WatchFiles** 实现 | 不是轮询 mtime，而是监听文件系统事件 | `[S3]` |
| 监控目录默认是**当前工作目录** | 所以 `.venv` 里的包变更也会触发重启 | `[S3]` |
| 父进程 PID ≠ 服务 PID | `/whoami` 返回的是子进程 PID | 实测 |
| 父进程不处理请求 | 杀掉父进程，子进程通常一起退出 | 实测 |

### 2.3 形态三：workers（`uvicorn main:app --workers N`）

```text
[父进程 master]  监听 socket、分配连接、管理子进程
      ├──> [worker 1] 处理请求
      ├──> [worker 2] 处理请求
      └──> [worker N] 处理请求
```

实测 `--workers 2`：

```text
INFO:     Started parent process [49976]
INFO:     Started server process [20432]
INFO:     Started server process [76292]
```

连续 30 次请求 `/whoami`：

```text
WORKERS2 samples: 30 unique pids: [20432, 76292]
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 请求被分发到 N 个进程 | 本机 30 次采样命中 2 个 PID | 实测 |
| 进程间**不共享内存** | 每个 worker 有独立的 Python 解释器 | `[S2]` |
| 端口由父进程监听 | 多个 worker 不会抢端口（SO_REUSEPORT/继承 fd） | `[S4]` |

> 注意：`--workers` 用的是**多进程**，不是多线程、不是协程。它的意义是绕开 GIL 做 CPU 并行，同时也意味着**模块级变量每进程一份**。第 2.5 节列了会因此失效的三类代码。`[S4]`

### 2.4 reload 的内部动作

```text
① 父进程启动，import 一次 app（为了尽早暴露语法错误）
② 父进程创建 WatchFiles 监听器，监控 --reload-dir 指定的目录
③ 父进程 spawn 子进程，子进程 import app 并开始监听请求
④ 文件变更 → WatchFiles 回调 → 父进程 terminate 子进程 → spawn 新子进程
⑤ 新子进程重新 import 模块 → 模块级代码重新执行 → 新配置生效
```

| 步骤 | 你能观察到的证据 | 依据 |
| --- | --- | --- |
| ② | 启动日志 `Will watch for changes in these directories: [...]` | 实测 |
| ③ | `Started server process [PID]` | 实测 |
| ④ | `WARNING: WatchFiles detected changes in 'main.py'. Reloading...` | 实测 |
| ⑤ | 新的 `Started server process` 行 + PID 变化 | **本机未观察到，见 4.4** |

### 2.5 三类在 workers 下会失效的代码

| 写法 | 单进程表现 | 多进程表现 | 替代 |
| --- | --- | --- | --- |
| `CACHE: dict[str, Any] = {}` 模块级缓存 | 命中率正常 | 每进程独立，命中率除以 N | Redis / 外部缓存 |
| `COUNTER = 0` 全局计数器 | 累加正确 | 每进程各数各的 | 数据库原子自增 / Redis INCR |
| `queue.Queue()` 内存队列 | 生产者消费者互通 | 各进程各一条队列，任务丢失 | Redis / MQ / `BackgroundTasks` 落库 |
| `asyncio.Lock()` 做跨请求互斥 | 有效 | 只在单进程内有效 | 分布式锁 |
| 启动时加载到内存的模型 | 一份 | 每进程一份，内存 × N | 调小 workers 或独立推理服务 |

> 注意：`--workers N` 会让内存占用接近 N 倍。一个占 500MB 的模型 × 4 workers = 2GB。这是「为了并发把内存吃爆」的最常见原因。`[S4]`

## 3. 参数全表

### 3.1 网络

| 参数 | 默认 | 作用 | 注意 | 依据 |
| --- | --- | --- | --- | --- |
| `--host` | `127.0.0.1` | 绑定地址 | 容器内必须 `0.0.0.0` | `[S1]` |
| `--port` | `8000` | 端口 | 被占报 `[Errno 10048]`，退出码 3 | 实测 |
| `--uds` | — | Unix socket 路径 | 同机通信比 TCP 快 | `[S1]` |
| `--fd` | — | 继承的文件描述符 | 由 systemd/supervisor 传 | `[S1]` |

### 3.2 重载

| 参数 | 默认 | 作用 | 依据 |
| --- | --- | --- | --- |
| `--reload` | 关 | 开启文件监听重启 | `[S3]` |
| `--reload-dir` | 当前目录 | 指定监控目录，可重复 | `[S3]` |
| `--reload-include` | — | 额外包含的 glob（如 `*.html`） | `[S3]` |
| `--reload-exclude` | — | 排除的 glob（如 `*.log`） | `[S3]` |
| `--reload-delay` | `0.25` | 两次检查的间隔（秒） | `[S3]` |

`--reload` 与 `--workers` 的实测结论：

```text
$ uvicorn main:app --reload --workers 2
WARNING:  "workers" flag is ignored when reloading is enabled.
```

| 结论 | 说明 |
| --- | --- |
| **不报错、不退出** | 服务正常起来（实测可访问） |
| `workers` 被**静默忽略** | 仍是单进程 |
| 只有一行 WARNING | 很容易被日志淹没 |

> 注意：这与很多旧文档「两者互斥会报错」的说法不同。本机 Uvicorn 0.54.0 的实测行为是**忽略 + WARNING**。写作时要区分「规范说互斥」与「当前版本实测行为」。`[S3]`

### 3.3 日志

| 参数 | 默认 | 作用 | 依据 |
| --- | --- | --- | --- |
| `--log-level` | `info` | `critical/error/warning/info/debug/trace` | `[S1]` |
| `--log-config` | — | 自定义 logging 配置文件 | `[S1]` |
| `--access-log` / `--no-access-log` | 开 | 是否打印访问日志 | `[S1]` |
| `--use-colors` | 自动 | 彩色日志 | `[S1]` |

访问日志格式（实测）：

```text
INFO:     127.0.0.1:49701 - "GET /whoami HTTP/1.1" 200 OK
```

| 字段 | 含义 |
| --- | --- |
| `127.0.0.1:49701` | 客户端 IP:源端口（**不是**服务端口） |
| `"GET /whoami HTTP/1.1"` | 请求行 |
| `200 OK` | 状态码与短语 |

### 3.4 代理与路径

| 参数 | 默认 | 作用 | 依据 |
| --- | --- | --- | --- |
| `--proxy-headers` / `--no-proxy-headers` | 开 | 是否信任 `X-Forwarded-For/Proto` | `[S4]` |
| `--forwarded-allow-ips` | `$FORWARDED_ALLOW_IPS` | 信任哪些代理 IP | `[S4]` |
| `--root-path` | `""` | ASGI `root_path`，反向代理子路径 | `[S4]` |

> 注意：`--proxy-headers` 默认是**开**的，但只在 `forwarded-allow-ips` 匹配时才生效。如果直接把服务暴露到公网又允许任意 IP 转发头，客户端可伪造 IP。第 54 章展开。`[S4]`

### 3.5 应用定位

| 参数 | 默认 | 作用 | 依据 |
| --- | --- | --- | --- |
| `--app-dir` | `""` | 把该目录加入 `sys.path` | `[S1]` |
| `--factory` | 关 | 把 `app` 当作工厂函数调用 | `[S1]` |

`--factory` 的典型用法：

```python
# main.py
def create_app() -> FastAPI:
    app = FastAPI()
    ...
    return app
```

```powershell
uvicorn main:create_app --factory
```

## 4. 边界条件

### 4.1 端口被占

实测（先用 socket 占住端口，再启动 uvicorn）：

```text
INFO:     Started server process [...]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
ERROR:    [Errno 10048] error while attempting to bind on address ('127.0.0.1', 54957):
          [winerror 10048] 通常每个套接字地址(协议/网络地址/端口)只允许使用一次。
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
rc: 3
```

| 事实 | 说明 |
| --- | --- |
| 退出码是 **3** | 脚本里可用 `$LASTEXITCODE -eq 3` 判断绑定失败 |
| 日志会先出现 `Application startup complete` | **顺序反直觉**：应用已启动完才报 bind 错 |
| 报错含 `10048`（Windows）/ `98`（Linux） | 排查时按这个码搜 |

| 排查顺序 | 命令 |
| --- | --- |
| 谁占了端口 | `Get-NetTCPConnection -LocalPort 8000 -State Listen` |
| 杀进程 | `Stop-Process -Id <PID> -Force` |
| 换端口 | `--port 8001` |

### 4.2 绑定地址选错

| 写法 | 谁能访问 | 场景 |
| --- | --- | --- |
| `--host 127.0.0.1` | 仅本机 | 本地开发 |
| `--host 0.0.0.0` | 所有网卡 | 容器、局域网、云主机 |
| `--host ::` | IPv6 全部 | 双栈环境 |

> 注意：Docker 里写 `127.0.0.1` 会导致「容器内能 curl，宿主机访问不了」。这是容器部署最高频的坑之一。`[S4]`

### 4.3 reload 监控范围过大

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 装个包就重启 | 监控了整个项目含 `.venv` | `--reload-dir app` |
| 写日志文件导致无限重启 | 日志文件在被监控目录内 | `--reload-exclude "*.log"` |
| 前端构建产物触发重启 | `dist/` 在监控范围 | `--reload-exclude dist` |
| CPU 占用高 | 监控目录过大 | 收窄 `--reload-dir` |

### 4.4 reload 打印 Reloading 但代码不生效（重点）

本机实测（Uvicorn 0.54.0 / Windows 11 / Python 3.12.8）：把 `main.py` 的返回值从 `{"version": 1}` 改成 `{"version": 2}`，日志出现：

```text
WARNING:  WatchFiles detected changes in 'main.py'. Reloading...
```

但 10 秒内反复请求，响应始终是 `{"version": 1}`，且**没有出现新的 `Started server process` 行**、`/whoami` 的 PID 也没变。

| 观察项 | 期望（生效） | 实测（未生效） |
| --- | --- | --- |
| 新 `Started server process` 行 | 有 | 无 |
| `/whoami` PID | 变化 | 不变 |
| 响应内容 | 新值 | 旧值 |

**排查清单（按命中概率排序）**：

| # | 原因 | 验证方法 | 解决 |
| --- | --- | --- | --- |
| 1 | 监控目录不包含改的文件 | 看 `Will watch for changes in` 的路径 | `--reload-dir` 指对 |
| 2 | 编辑器「安全写入/原子保存」导致事件被忽略 | 用 `echo` 追加一行再试 | 关掉原子保存，或改 `--reload-delay` |
| 3 | 改的是 `import` 进来的子模块，但子模块没被监控 | 看监控目录是否含该文件 | 扩大 `--reload-dir` |
| 4 | Docker 卷挂载不传播 inotify 事件 | 进容器 `touch` 文件试 | 用轮询类工具，或挂载一致 |
| 5 | 旧 `.pyc`/`__pycache__` 干扰 | 删 `__pycache__` 重试 | 清理缓存 |
| 6 | 端口上有**另一个**旧进程仍在服务 | `Get-NetTCPConnection` 看 PID | 杀掉旧进程 |
| 7 | 服务器实现本身的 bug/平台差异 | 换 `fastapi dev` 复测 | 升级 uvicorn 或换启动器 |

> 注意：第 6 条最容易被忽略——你以为 reload 没生效，其实是旧服务还占着端口，新服务根本没起来（`[Errno 10048]` 被日志淹没）。**先确认端口上的 PID 是不是你刚启动的那个。**

### 4.5 优雅退出

| 信号 | 行为 | 依据 |
| --- | --- | --- |
| `SIGINT`（Ctrl+C） | 等待在途请求结束，再关闭 | `[S1]` |
| `SIGTERM`（kill） | 同上，容器编排用这个 | `[S1]` |
| `SIGKILL`（kill -9） | 立即终止，连接被重置 | `[S1]` |

| 事实 | 说明 |
| --- | --- |
| `lifespan` 的 shutdown 只在优雅退出时执行 | 被 `kill -9` 不会执行清理 |
| 容器 `terminationGracePeriodSeconds` 要大于最长请求耗时 | 否则请求被硬切断 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `--reload --workers 4` | 实测仅 WARNING，workers 被忽略 | 分两条命令 | 实测 |
| 认为 reload 会影响生产性能 | 生产根本不该开 reload | 生产 `--workers` | `[S3]` |
| `--host 127.0.0.1` 跑容器 | 外部访问不通 | `0.0.0.0` | `[S4]` |
| 把 `reloader process` 的 PID 当服务 PID | 监控/杀进程错位 | 认 `Started server process` | 实测 |
| 8000 被占只看最后一行日志 | 误以为启动成功 | 看退出码 3 与 `10048` | 实测 |
| 用 `python main.py` 想要热重载 | 改代码不生效 | `uvicorn main:app --reload` | `[S3]` |
| `uvicorn.run(app, reload=True)` | 传对象时 reload 无效/报错 | 传字符串 `"main:app"` | `[S3]` |
| 在 `src/` 布局下直接 `uvicorn main:app` | `Could not import module` | `--app-dir src` | `[S1]` |
| 监控整个仓库 | 装依赖就重启 | `--reload-dir app` | `[S3]` |
| 日志写进被监控目录 | 无限重启 | `--reload-exclude "*.log"` | `[S3]` |
| 多进程下用模块级 dict 缓存 | 命中率骤降、数据不一致 | Redis | `[S4]` |
| 多进程下用全局计数器统计 QPS | 数字只有真实值的 1/N | 外部存储 | `[S4]` |
| 多进程下用内存队列派发任务 | 任务丢在某个进程里 | MQ / DB | `[S4]` |
| 多进程下用 `asyncio.Lock` 做全局互斥 | 只在单进程内互斥 | 分布式锁 | `[S4]` |
| workers 设为 CPU 核数的 4 倍 | 内存爆、上下文切换多 | 一般核数 ~ 2 倍 | `[S4]` |
| 大模型服务开 8 workers | 内存 × 8 直接 OOM | 单进程 + 异步 / 独立推理服务 | `[S4]` |
| 用 reload 模式压测 | 结果毫无参考价值 | 用 workers 模式压 | `[S4]` |
| 改了代码只看 IDE 保存状态 | 文件没真正落盘 | 看日志 `detected changes` | 实测 |
| reload 打印 Reloading 就认为生效 | 实测可能未重启 | 看 PID 与响应内容 | 实测 |
| 端口上还有旧进程 | 新服务绑不上，旧服务继续应答 | 先查 PID | 实测 |
| 生产用 Ctrl+C 停止 | 容器编排发的是 SIGTERM | 处理好优雅退出 | `[S1]` |
| `kill -9` 停服务 | lifespan 清理不执行、连接重置 | SIGTERM | `[S1]` |
| 忽略 `--proxy-headers` 的信任范围 | 客户端可伪造 IP | 配 `--forwarded-allow-ips` | `[S4]` |
| 用 `--root-path` 代替网关配置 | 路由与静态资源仍错 | 网关与 app 两侧都配 | `[S4]` |
| `--log-level debug` 上生产 | 日志量爆炸 | `info` | `[S1]` |
| 关掉 access log 后无法排查 | 没有请求记录 | 用结构化日志中间件替代 | 第 52 章 |
| 用 `print` 当启动日志 | 无时间戳、无级别、多进程交错 | `logging` | `[S8]` |
| 把 `uvicorn.run()` 写在 import 期 | 测试导入时也起服务 | 放 `if __name__ == "__main__"` | `[S1]` |
| `--reload-delay` 设得极小 | CPU 空转 | 默认 0.25 够用 | `[S3]` |
| 用 `--workers` 又用模块级单例连接池 | 每进程一个池，总数 × N | 按进程数调整池大小 | 第 55 章 |
| 期待 workers 之间共享 `lifespan` 状态 | 每个 worker 各跑一次 startup | 状态落外部存储 | 第 67 章 |
| 在 reload 模式下调试断点 | 重启后调试器断开 | 调试用无 reload | 第 75 章 |
| Windows 上用 `uvicorn` 无 `[standard]` | reload 退化为轮询/不可用 | 装 `uvicorn[standard]` | `[S3]` |
| 端口用字符串 `--port "8000"` | 部分版本解析异常 | 用整数 | `[S1]` |
| 同时开两个 reload 实例 | 抢端口、互相重启 | 一个项目一个 | 实测 |
| 用 `nohup` 后忘了 PID | 无法优雅停止 | 进程管理器 | `[S4]` |
| 忽略启动耗时 | 每次重启 2–10 秒，调试体验差 | 收窄监控 + 延迟导入 | `[S3]` |
| 把 `--reload` 写进 Dockerfile CMD | 生产带监控进程 | 用环境区分 | `[S4]` |
| `fastapi dev` 与 `uvicorn` 参数混用 | 部分参数不识别 | 各自查 `--help` | `[S3]` |

## 6. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 开发命令固定为 `uvicorn main:app --reload --reload-dir app` | 收窄监控范围，避免装包就重启 | `[S3]` |
| 生产命令固定为 `uvicorn main:app --host 0.0.0.0 --workers N --no-access-log` | 访问日志交给网关或结构化中间件 | `[S4]` |
| workers 数从「CPU 核数」起调，不超 2 倍 | 内存与切换成本 | `[S4]` |
| 启动命令写进脚本，不靠手打 | 团队一致、可追溯 | 第 76 章 |
| `/whoami` 这类观测接口只在开发环境开 | 避免泄露环境信息 | `[S4]` |
| 应用启动失败要 fail fast | 配置缺失就退出，不要带病运行 | 第 66 章 |
| 用 `--factory` 配合工厂函数 | 便于测试注入不同配置 | `[S1]` |
| 日志级别用环境变量控制 | 生产 info、排障时 debug | 第 52 章 |

**命令清单（可直接抄）**：

```powershell
# 开发
uv run uvicorn main:app --reload --reload-dir . --reload-exclude "*.log" --port 8000

# 生产（Linux 容器内）
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --no-access-log

# 只验证能否导入（CI 用，不监听端口）
uv run python -c "import main; print(main.app.title)"
```

**边界**：

- 本章所有进程结论都在 Windows 11 + Uvicorn 0.54.0 下得出；Linux 上 reload 的 `fork` 语义更可靠，4.4 节的现象**未必复现**。
- `--workers` 的负载分发由操作系统决定（accept 竞争），**不保证轮询**，实测 30 次请求命中 2 个进程但比例不固定。
- 本章不涉及反向代理与容器，相关坑在第 54、76 章。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[S1]` | 官方文档 | https://www.uvicorn.org/ | 命令行参数、信号处理、`--factory`、`--log-level` |
| `[S2]` | 规范 | https://asgi.readthedocs.io/en/latest/ | ASGI 应用接口、`scope/receive/send` |
| `[S3]` | 官方文档 | https://fastapi.tiangolo.com/zh/fastapi-cli/ | `fastapi dev`、reload 行为 |
| `[S4]` | 官方文档 | https://fastapi.tiangolo.com/zh/deployment/ | 多进程、`--proxy-headers`、容器部署 |
| `[S5]` | 官方文档 | https://www.starlette.io/lifespan/ | 应用启停与优雅退出 |
| `[S6]` | 工具文档 | https://watchfiles.helpmanual.io/ | WatchFiles 监控机制与过滤规则 |
| `[S7]` | 规范 | https://peps.python.org/pep-3333/ | WSGI 到 ASGI 的演进背景 |
| `[S8]` | 官方文档 | https://docs.python.org/3/library/logging.html | 日志级别与格式 |

> **核对状态**：`[S1]`–`[S8]` 按官方文档结构整理，**未逐页直连复核**（本次网络受限）。文中「实测」为 Uvicorn 0.54.0 / Windows 11 / Python 3.12.8 的真实输出，可通过 `verify.py` 与 README 的命令复现；4.4 节的「Reloading 但未重启」是本机实测结论，不同平台/版本可能不同，已在正文标注。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] ASGI 服务器与 ASGI 应用的分工
- [ ] `main:app` 这个导入路径的含义
- [ ] 三种进程形态的进程树结构
- [ ] `reloader process` 与 `server process` 的区别
- [ ] `--reload` 与 `--workers` 的语义差异
- [ ] WatchFiles 与「轮询 mtime」的区别

**能写出（代码层）**：

- [ ] 带 `/whoami` 的观测接口
- [ ] 开发与生产两条启动命令
- [ ] `--factory` 形式的工厂函数
- [ ] 用 `--reload-dir` / `--reload-exclude` 收窄监控

**能判断（避坑层）**：

- [ ] 看到 `--reload --workers` 能指出 workers 被忽略
- [ ] 看到退出码 3 能想到端口占用
- [ ] 看到容器里写 `127.0.0.1` 能指出访问不通
- [ ] 看到多进程 + 模块级 dict 能指出数据不一致
- [ ] 看到「Reloading 但没生效」能列出 7 项排查
- [ ] 看到 workers 数 = CPU×8 能指出内存风险

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 6/6 通过
- [ ] `--workers 2` 下请求 20 次出现 2 个 PID
- [ ] 复现端口占用：占住端口再启动，看到 `10048` 与退出码 3
- [ ] 复现 `--reload --workers` 的 WARNING

## 9. 下一章衔接

第 03 章 `路由与 HTTP 方法`：同一个 app 上注册四种方法，讲清路由匹配顺序（`/items/{id}` 会吃掉 `/items/latest`）、405 的 `Allow` 头、`api_route` 多方法注册、`url_path_for` 反向解析。

本章留下的伏笔：

1. workers 多进程与「进程内状态」的冲突——第 66 章配置、第 55 章连接池继续。
2. 访问日志格式——第 52 章改用结构化日志 + `trace_id`。
3. `--root-path` 与 `--proxy-headers`——第 54 章展开。
