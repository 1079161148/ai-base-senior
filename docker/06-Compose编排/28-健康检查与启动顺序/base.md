# 28 健康检查与启动顺序 · 完整版

## 0. 怎么用

跑 17/17。本章解决一个非常具体的生产事故：**"容器都在跑，应用就是连不上数据库"**。答案通常是 `depends_on` 用错了条件，或者根本没定义健康检查。

## 1. 三个容易混淆的概念

| 概念 | 回答的问题 | 谁负责 |
| --- | --- | --- |
| 启动顺序 | 谁先启动 | `depends_on` |
| 是否可用 | 起来了但能不能干活 | `healthcheck` |
| 挂了怎么办 | 退出后要不要重启 | `restart` |

**三者互不替代。** 最常见的错误是以为 `depends_on` 能解决"数据库还没 ready"，实际上默认条件只是"容器 running"——Postgres 容器 running 的那一刻，5432 端口通常还在初始化。

## 2. 健康检查机制

### 2.1 状态机

```text
创建 ──► starting ──连续成功──► healthy
            │                     │
            │                连续失败 retries 次
            │                     ▼
            └─ start_period 内 ──► unhealthy
               （失败不计数）
```

关键细节：

| 细节 | 说明 |
| --- | --- |
| 首次检查时机 | 容器启动后立即开始，间隔 `interval` |
| `start_period` 内失败 | 不计入 `retries`，状态保持 `starting` |
| `start_period` 结束后 | 每次失败累加 `FailingStreak`，达 `retries` 变 `unhealthy` |
| 恢复 | `unhealthy` 后检查仍继续，成功即回 `healthy` |
| 退出码 2 | 保留状态不变（不用这个就别用） |

实测证据：`probe` 配 `start_period: 30s` + `test -f /tmp/ready`，`up -d` 后立刻 inspect：

```text
starting                      # 检查实际已失败，但在宽限期内
docker exec ... touch /tmp/ready
→ healthy                     # 2 秒内（interval=2s）
```

`start_period` 的意义：**区分"启动慢"和"真挂了"**。没有它，一个需要 60 秒初始化的应用会被 3 次失败直接打成 `unhealthy`。

### 2.2 test 的三种写法

```yaml
test: ["CMD", "pg_isready", "-U", "app"]        # exec 形式，不经过 shell
test: ["CMD-SHELL", "pg_isready -U $POSTGRES_USER"]  # shell 形式，变量会展开
test: pg_isready -U app                          # 字符串 = CMD-SHELL
```

坑点：`CMD` 形式**不做变量展开**，也不支持 `||`、`&&`、管道。要这些就用 `CMD-SHELL`。

### 2.3 一个真实可用的检查表

| 服务 | 检查命令 | 理由 |
| --- | --- | --- |
| PostgreSQL | `pg_isready -U app -d appdb` | 官方提供，比 `nc -z` 准（能发现只读/恢复中） |
| MySQL | `mysqladmin ping -h 127.0.0.1 -u root -p$PW` | 见第 13 章踩坑：初始化期间会误报 |
| Redis | `redis-cli ping` | 返回 `PONG` |
| Nginx | `wget -q -O /dev/null http://127.0.0.1/` | 用 `127.0.0.1` 不用 `localhost` |
| 自研 HTTP 服务 | `python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz')"` | 镜像里不一定有 curl |

**注意**：`localhost` 在容器里可能先解析到 `::1`，而应用只监听 IPv4，检查直接失败。统一写 `127.0.0.1`。

### 2.4 镜像里的 HEALTHCHECK 与 compose 的关系

第 22 章在 Dockerfile 里写过 `HEALTHCHECK`。compose 中再写 `healthcheck` 会**整体覆盖**镜像的定义（不是合并）：

| 场景 | 结果 |
| --- | --- |
| 只有 Dockerfile `HEALTHCHECK` | 容器带健康状态 |
| 只有 compose `healthcheck` | 生效（本章 `web` 服务演示：nginx 镜像本身没有） |
| 两者都有 | compose 的赢 |

关掉镜像自带的检查：

```yaml
healthcheck:
  disable: true
```

## 3. depends_on 的三种条件

### 3.1 语法差异

```yaml
# 短语法 = service_started，不等就绪
depends_on: [db]

# 长语法，能指定条件
depends_on:
  db:
    condition: service_healthy
    restart: true            # 依赖重建时一并重建本服务
```

### 3.2 实测对比

`slowdb` 启动后先 `sleep 8`，然后才开始 `nc -l -p 5432`。

| 消费者 | 条件 | 实际日志 |
| --- | --- | --- |
| `consumer_started` | `service_started` | `NOT_READY` |
| `consumer_healthy` | `service_healthy` | `CONNECTED` |

这就是"容器都在跑但连不上"的最小复现。修法只有两种：**改条件**，或者**应用层加重试**。生产建议两者都做——`depends_on` 管首次启动，重试管运行期断连（数据库重启、网络抖动）。

### 3.3 service_completed_successfully

本章没演示，但生产常用：

```yaml
services:
  migrate:
    image: myapp:v1
    command: ["python", "manage.py", "migrate"]
    depends_on:
      db: {condition: service_healthy}
  api:
    image: myapp:v1
    depends_on:
      migrate: {condition: service_completed_successfully}
```

`migrate` 跑完退出码 0，`api` 才开始构建——这是"一次性任务"的正确编排方式。

## 4. restart 策略

| 值 | 触发 | 注意事项 |
| --- | --- | --- |
| `"no"` | 不重启 | 默认值；`docker run` 的默认也是它 |
| `always` | 任何退出 | 正常退出的任务会被反复拉起，**别给一次性任务用** |
| `on-failure` | 非 0 退出 | 无限重试 |
| `on-failure:3` | 非 0 退出，最多 3 次 | 实测：`RestartCount=3` 后 `exited`，`ExitCode=1` |
| `unless-stopped` | 除人为 stop | 生产最常用：宿主重启后自动拉起 |

重启有**指数退避**（100ms 起，翻倍，上限 1 分钟），所以 `RestartCount` 增长不会太暴力。

### 4.1 实测数据

| 服务 | 配置 | 结果 |
| --- | --- | --- |
| `crasher` | `sh -c "sleep 1; exit 1"` + `on-failure:3` | 重启 3 次后 `exited`，退出码 1 |
| `steady` | 同上 + `restart: "no"` | `RestartCount=0`，立刻 `exited` |

### 4.2 unhealthy 不会触发重启

这是最容易被误解的一点。容器进程活着，只是健康检查失败 → 状态 `unhealthy`，**Docker 不会重启它**。

| 需求 | 方案 |
| --- | --- |
| 进程崩溃自动恢复 | `restart: unless-stopped` |
| 卡死/假活自动恢复 | 外部 autoheal 容器，或 K8s livenessProbe |
| 只是不想把流量打过去 | 反代/网关按健康状态摘流量 |

```yaml
# autoheal 思路：监听 unhealthy 事件并重启对应容器
services:
  autoheal:
    image: willfarrell/autoheal
    environment:
      AUTOHEAL_CONTAINER_LABEL: all
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

## 5. up --wait：把"就绪"变成命令的返回值

```bash
docker compose up -d --wait                    # 全部 healthy 才返回 0
docker compose up -d --wait --wait-timeout 60
```

实测：`ready` 服务需要 4 秒才创建标记文件，`up -d --wait` 耗时 **> 4s** 才返回，返回时状态已是 `healthy`。

这是 CI 与集成测试里的正确用法：**先 `--wait`，再跑测试**，避免"容器刚起来就访问"的偶发失败。

> 实测补充（本机 Compose v5.3.1）：`--wait-timeout` 到点时，在交互终端里打印 `application not healthy after 2s` 并返回退出码 1；而在非 TTY 的管道调用下，观察到退出码为 0。**脚本里不要只看退出码，配合 `docker inspect` 复核状态。**

## 6. 逐条验收解读（17 条）

| 组 | 证明了什么 |
| --- | --- |
| 1 | `up -d` 会按 `service_healthy` 依赖链串行启动 |
| 2 | 未定义检查的服务没有健康状态 |
| 3–4 | `start_period` 内是 `starting`，条件满足后转 `healthy` |
| 5–6 | 持续失败会 `unhealthy`，`FailingStreak` 达阈值 |
| 7 | 镜像没定义检查时，compose 可以补 |
| 8–9 | 两种 `condition` 的行为差异（核心） |
| 10 | 依赖最终 healthy |
| 11–14 | `on-failure:3` / `no` 的重启与退出码语义 |
| 15–17 | `--wait` 阻塞到就绪、返回即 healthy、耗时确实 > 4s |

## 7. 坑与对策

| 现象 | 根因 | 对策 |
| --- | --- | --- |
| `NOT_READY` / `Connection refused` | `service_started` 不等就绪 | `service_healthy` + 应用重试 |
| 检查命令 `not found` | 基础镜像没有 curl/wget | 用镜像里有的工具，或 `CMD-SHELL` 组合 |
| `$VAR` 没展开 | 用了 `CMD` | 改 `CMD-SHELL` |
| 一直 `starting` | `start_period` 很长 | 确认应用真的就绪，别把宽限期当遮羞布 |
| 一直 `unhealthy` | 检查写错（端口/IPv6/路径） | `docker inspect .State.Health.Log` 看输出 |
| `--wait` 卡住 | 某服务永远不 healthy | 先修检查，再配 `--wait-timeout` |
| `always` 让任务无限重启 | 一次性任务用了 `always` | 用 `on-failure` 或 `"no"` |
| 数据库重启后应用报错 | 运行期断连 | 重试/连接池/健康探测 |
| 健康检查把 CPU 打满 | `interval: 100ms` + 重检查 | 间隔 ≥ 5s，检查做轻量动作 |
| 改了检查没生效 | 容器没重建 | `up -d --force-recreate` |

## 8. 生产实践模板

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 30s

  api:
    image: registry.example.com/app:1.4.2
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 20s
```

注意 `$${POSTGRES_USER}`：Compose 里 `$` 需要转义成 `$$`，让变量留给**容器内**的 shell 展开，而不是被 Compose 提前替换。

## 9. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Compose `depends_on` / `healthcheck` 参考、Dockerfile `HEALTHCHECK`、restart policy 文档 |
| `[r3]` | 实测 | 17/17；`starting`→`healthy` 状态转移、两种 condition 的日志差异、`on-failure:3` 的 `RestartCount=3`、`--wait` 阻塞时长为本机实录 |

## 10. 毕业自查

- [ ] 17/17 通过
- [ ] 能背出健康检查四个参数与默认值
- [ ] 能解释 `start_period` 与 `retries` 的配合
- [ ] 能说出三种 condition 的差别与适用场景
- [ ] 能解释为什么 `unhealthy` 不等于自动重启
- [ ] 能写出一个应用级 `/healthz` 并说明它检查什么
- [ ] 知道 `$$` 在 Compose 里的用途

## 11. 下一章

第 29 章进入 Compose 生产实践：`profiles`、`secrets`、多文件 override、`extends`/`include`、资源限制与 `--scale`。
