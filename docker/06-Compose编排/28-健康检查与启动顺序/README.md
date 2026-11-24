# 28 健康检查与启动顺序

## 一句话结论

`depends_on` 只管**启动顺序**，`condition: service_healthy` 才能等到**真正可用**；`healthcheck` 只负责**打标签**（starting/healthy/unhealthy），它不会自动重启容器——"自动恢复"是 `restart` 策略和编排平台的活。

## 最小可运行案例

```yaml
services:
  db:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d appdb"]
      interval: 3s
      timeout: 3s
      retries: 20
      start_period: 10s

  api:
    image: python:3.12-slim
    depends_on:
      db:
        condition: service_healthy      # ← 只有这个会等就绪
```

## 怎么跑

```powershell
cd "06-Compose编排\28-健康检查与启动顺序\examples"
uv run python verify.py
```

## 本机实测（17/17）

| 断言 | 实测 |
| --- | --- |
| 未定义 healthcheck 的容器 | `State.Health` 为空（`none`） |
| `start_period: 30s` 内检查失败 | 状态停在 `starting` |
| 手工创建标记文件后 | 2 秒内转 `healthy` |
| 永远失败的检查（retries 2） | 变 `unhealthy`，`FailingStreak >= 2` |
| 镜像没定义健康检查 | compose 里补 `healthcheck` 后同样 `healthy` |
| `condition: service_started` 的消费者 | 日志 `NOT_READY`（依赖还没监听） |
| `condition: service_healthy` 的消费者 | 日志 `CONNECTED` |
| `restart: on-failure:3` | `RestartCount` = 3 后 `exited`，退出码保留 1 |
| `restart: "no"` | `RestartCount` = 0 |
| `up -d --wait` | 阻塞 4 秒以上，返回时已 `healthy` |

## 三种状态

```text
容器启动 ──► starting ──健康检查通过──► healthy
                 │                        │
                 │                   失败达 retries
                 │                        ▼
                 └── 仍在 start_period ──► unhealthy
                     （失败不计入 retries）
```

| 状态 | 含义 | 排查方向 |
| --- | --- | --- |
| `starting` | 检查还没通过，或仍在 `start_period` | 正常等待；启动慢就加大 `start_period` |
| `healthy` | 连续成功 | — |
| `unhealthy` | 连续失败达 `retries` | `docker inspect .State.Health.Log` 看最后一次输出 |

## 参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `test` | — | `["CMD", ...]` 不走 shell；`["CMD-SHELL", "…"]` 走 shell |
| `interval` | 30s | 检查间隔 |
| `timeout` | 30s | 单次检查超时 |
| `retries` | 3 | 连续失败几次判 `unhealthy` |
| `start_period` | 0s | 启动宽限期，期间失败不计入 `retries` |

`test` 的退出码语义：**0 = 健康，1 = 不健康，2 = 保留（不改变状态）**。

```yaml
# 三种写法等价
test: ["CMD-SHELL", "curl -fsS http://127.0.0.1/ || exit 1"]
test: ["CMD", "curl", "-fsS", "http://127.0.0.1/"]
test: curl -fsS http://127.0.0.1/ || exit 1      # 字符串形式 = CMD-SHELL
```

## depends_on 的三种条件

| condition | 何时启动下游 | 适用 |
| --- | --- | --- |
| `service_started`（默认） | 依赖容器 `running` 就启动 | 无状态、可重试 |
| `service_healthy` | 依赖变 `healthy` | 数据库、消息队列 |
| `service_completed_successfully` | 依赖**成功退出**（码 0） | 迁移脚本、一次性任务 |

本章实测对比最能说明问题：

| 消费者 | 条件 | 日志 |
| --- | --- | --- |
| `consumer_started` | `service_started` | `NOT_READY` |
| `consumer_healthy` | `service_healthy` | `CONNECTED` |

依赖服务的 `slowdb` 故意 8 秒后才开始监听 5432。

## restart 策略

| 值 | 行为 |
| --- | --- |
| `"no"`（默认） | 不重启 |
| `always` | 任何退出都重启（含正常退出） |
| `on-failure[:max]` | 非 0 退出才重启，最多 `max` 次 |
| `unless-stopped` | 除非人为 stop，否则重启（含 Docker 重启后恢复） |

实测 `on-failure:3`：`RestartCount` 停在 3，状态 `exited`，`ExitCode` 仍是 1。

**`restart` 与 `healthcheck` 是两件事**：

| | restart | healthcheck |
| --- | --- | --- |
| 触发条件 | 进程退出 | 检查失败 |
| 结果 | 重启容器 | 只改状态标签 |
| 解决什么 | 崩溃 | 卡死/假活 |

容器活着但 `unhealthy` 时**不会自动重启**。要自动处理需外部工具（如 `willfarrell/autoheal`）或 K8s 的 livenessProbe。

## 常用命令

```bash
docker inspect -f '{{.State.Health.Status}}' <容器>
docker inspect -f '{{json .State.Health.Log}}' <容器> | jq '.[-1]'
docker inspect -f '{{.State.Health.FailingStreak}}' <容器>
docker compose up -d --wait                 # 等全部 healthy 才返回
docker compose up -d --wait --wait-timeout 60
docker compose ps                           # 含健康状态列
docker compose events                       # 实时事件（health_status 也在里面）
```

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `depends_on` 写了还是 `Connection refused` | 默认 `service_started` | 改 `service_healthy` |
| 健康检查一直 `unhealthy`，服务其实正常 | 镜像里没有 `curl` | 用 `wget -q -O /dev/null` 或改 `CMD-SHELL` |
| 启动慢的服务被判死 | `start_period` 太短 | 调大或增加 `retries` |
| `CMD` 里 `$VAR` 不展开 | `CMD` 不走 shell | 用 `CMD-SHELL` |
| 检查"自己"却报错 | 应用监听 `0.0.0.0` 但检查写 `localhost` 解析到 IPv6 | 用 `127.0.0.1` |
| `unhealthy` 后容器还在跑 | 健康检查只打标签 | 配 autoheal 或编排平台 |
| `--wait` 一直不返回 | 有服务永远不 `healthy` | 加 `--wait-timeout`，先修检查 |
| 数据库重启后应用连不上 | `depends_on` 只在启动时生效 | 应用层加重试/连接池 |
| 健康检查拖慢启动 | `interval` 太小 + 检查重 | 间隔 ≥ 5s，检查做轻量动作 |

## 生产建议

| 层 | 检查什么 | 示例 |
| --- | --- | --- |
| 存活（liveness） | 进程是否卡死 | `test -f /tmp/alive` |
| 就绪（readiness） | 依赖是否可用 | `/healthz` 里探测 DB/Redis |
| 启动（startup） | 冷启动是否完成 | `start_period` 给足 |

一个 `/healthz` 至少覆盖：进程能响应 HTTP、关键依赖能连通、必要的初始化已完成。**不要**在健康检查里做重操作（全表扫描、外部大 API 调用）。

## 毕业自查

- [ ] 17/17 通过
- [ ] 能画出 `starting → healthy / unhealthy` 的状态机
- [ ] 能解释 `start_period` 与 `retries` 的区别
- [ ] 能说出三种 `condition` 各自的适用场景
- [ ] 能解释为什么 `unhealthy` 不会自动重启容器
- [ ] 知道 `CMD` 与 `CMD-SHELL` 在变量展开上的差异
