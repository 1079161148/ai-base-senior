# 36 毕业项目与排障手册 · 完整版

## 0. 怎么用

跑 22/22。这是全教程的收尾：用一个可发布/可回滚的小项目串起前面所有能力，再把八类真实故障的错误原文与诊断命令固定下来。

## 1. 毕业项目结构

```text
examples/
├── Dockerfile          # ARG APP_VERSION + 非 root + HEALTHCHECK
├── app.py              # /version /healthz /crash
├── compose.yaml        # image: ch36-app:${APP_VERSION}
├── .env.v1 / .env.v2    # 两个"发布版本"
└── verify.py           # 22 条验收
```

设计意图：

| 设计 | 目的 |
| --- | --- |
| 版本通过 `ARG` 注入并写进 `LABEL`/`ENV` | 发布可追溯 |
| `/version` 返回真实版本 | 验证"流量打到哪个版本" |
| `/healthz` | 就绪判定 |
| `/crash` 触发退出码 3 | 演练故障 |
| compose 用变量决定镜像 tag | 回滚只需换 env |

## 2. 发布与回滚机制

### 2.1 `up -d` 做了什么事（实测）

```bash
docker compose --env-file .env.v1 up -d     # 创建 app 容器（ch36-app:v1）
docker compose --env-file .env.v2 up -d     # 检测到 image 变了 → 重建
```

| 断言 | 结果 |
| --- | --- |
| `/version` | `v1` → `v2` |
| 容器 ID | 变化（不是原地重启） |
| `compose ps -q` 数量 | 1（旧容器被删除，不是叠加） |

这就是 Compose 的"差异更新"：**配置或镜像变了才重建**，否则容器不动。

### 2.2 回滚

```bash
docker compose --env-file .env.v1 up -d      # 换回 v1
```

实测 `/version` 回到 `v1`。前提是**旧镜像还在本地/仓库**——所以生产禁止覆盖 tag。

### 2.3 零停机要点

| 要点 | 说明 |
| --- | --- |
| `up -d --wait` | 等新容器 healthy 再返回 |
| 反代按健康摘流量 | 单机 Compose 需自己配 Nginx/Traefik |
| 迁移脚本兼容双版本 | 先加列后删列，别一次改死 |
| 会话外置 | 放 Redis，重启不丢 |

单机 Compose 不是真正的滚动更新（容器会先停后起，有秒级中断）。要零停机得上 Swarm/K8s 或蓝绿/双实例 + 反代。

## 3. 排障方法论

### 3.1 先分层定位

```text
第 1 层 应用      进程退出、异常栈、配置缺失      → docker logs, ExitCode
第 2 层 镜像      CMD/ENTRYPOINT、缺二进制、架构   → run --entrypoint sh
第 3 层 容器      端口、挂载、限制、信号           → inspect, port, diff
第 4 层 网络      DNS、端口映射、隔离             → exec + 服务名
第 5 层 存储      卷、权限、空间                   → volume inspect, df
第 6 层 宿主/daemon  磁盘、内存、日志驱动、代理     → info, system df, events
```

**先判断落在哪一层，再选命令**，比盲目 `docker inspect` 快得多。

### 3.2 本章实测的八类故障原文

| # | 故障 | 关键证据 |
| --- | --- | --- |
| ① | 应用异常退出 | `run` 退出码 3 |
| ② | 启动即崩 | `logs` 里 `fatal: missing config`，`ExitCode=7` |
| ③ | 端口冲突 | `docker run` 非 0，报错明确 |
| ④ | 容器名冲突 | `container name "/ch36-capstone-app-1" is already in use` |
| ⑤ | 健康检查 | 镜像级 `HEALTHCHECK` 生效；`.State.Health.Log` 含 `ExitCode` |
| ⑥ | 信号处理 | 无 `--init` → 137；有 `--init` → 143 |
| ⑦ | 配置漂移 | `docker diff` → `A /home/appuser/drift.txt` |
| ⑧ | 磁盘占用 | `docker system df` 输出 Images/Containers |

### 3.3 ⑥ 值得单独讲：PID 1 与信号

容器里 PID 1 的进程对**未注册处理函数的信号不执行默认动作**（内核保护 init 进程）。所以：

```text
python app.py 作为 PID 1
  → docker stop 发 SIGTERM
  → python 忽略（无 handler，且是 PID 1）
  → 10 秒后 SIGKILL
  → ExitCode = 137
```

三种修法实测/推荐：

| 修法 | 效果 |
| --- | --- |
| `docker run --init` | tini 作 PID 1，转发信号 → 143 |
| Dockerfile 里 `ENTRYPOINT ["tini","--"]` | 镜像自带 init |
| 应用注册 handler | `signal.signal(SIGTERM, ...)` 清理后退出 |

这也是"为什么我的容器停止要等 10 秒"的根因。

## 4. 命令速查（按排查顺序排）

```bash
# 一、看状态
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
docker inspect -f '{{.State.Status}} {{.State.ExitCode}} {{.State.OOMKilled}}' <容器>
docker inspect -f '{{json .State.Health}}' <容器> | jq

# 二、看日志
docker logs --tail 200 <容器>
docker logs --since 10m <容器> 2>&1 | grep -iE "error|fatal|panic"

# 三、进容器
docker exec -it <容器> sh
docker exec -it <容器> netstat -tlnp 2>/dev/null || docker exec -it <容器> ss -tlnp

# 四、看差异与资源
docker diff <容器>
docker stats --no-stream
docker system df -v

# 五、看配置终态
docker compose config
docker inspect -f '{{json .HostConfig}}' <容器> | jq
docker inspect -f '{{json .Mounts}}' <容器> | jq
docker inspect -f '{{json .NetworkSettings.Networks}}' <容器> | jq

# 六、事件流
docker events --since 10m --filter container=<容器>
```

## 5. 退出码与信号

| 退出码 | 信号 | 典型原因 |
| --- | --- | --- |
| 0 | — | 正常结束（长驻服务出现即异常） |
| 1 | — | 应用错误 |
| 2 | — | shell 语法/参数错误 |
| 125 | — | docker 自身失败（参数冲突） |
| 126 | — | 命令不可执行（权限） |
| 127 | — | 命令不存在 |
| 137 | 9 (SIGKILL) | OOM 或 stop 超时强杀 |
| 143 | 15 (SIGTERM) | 优雅停止 |

排查 137 的两条分支：

```bash
docker inspect -f '{{.State.OOMKilled}}' <容器>   # true → 加内存
docker inspect -f '{{.HostConfig.Init}}' <容器>   # null/false → 考虑 --init
```

## 6. 常见报错原文对照

| 报错 | 层 | 处理 |
| --- | --- | --- |
| `port is already allocated` | 容器 | 换端口或停掉占用容器 |
| `container name ... is already in use` | 容器 | `docker rm` 旧容器 |
| `no space left on device` | 宿主 | `system df` + 日志轮转 + prune |
| `permission denied`（挂载） | 存储 | 命名卷 / chown / `:ro` 检查 |
| `exec format error` | 镜像 | 架构不匹配，重建正确平台镜像 |
| `standard_init_linux.go: exec user process caused` | 镜像 | ENTRYPOINT/shebang |
| `TLS handshake timeout` | 网络 | daemon 代理/镜像加速 |
| `conflict: unable to delete ... image is being used` | 容器 | 先删容器再删镜像 |
| `network ... has active endpoints` | 网络 | 先断开/删容器 |
| `invalid reference format` | 命名 | 检查 tag/仓库名大小写 |

## 7. 逐条验收解读（22 条）

| 组 | 覆盖内容 |
| --- | --- |
| 1–2 | 两个版本镜像构建 |
| 3–6 | 首次发布、版本正确、发布 v2 后版本切换、容器 ID 变化 |
| 7 | 不叠加部署（容器数 1） |
| 8–9 | 回滚成功且版本正确 |
| 10 | 异常退出码保留 |
| 11–12 | 崩溃原因可从 logs 与 ExitCode 读取 |
| 13–14 | 端口冲突、名称冲突报错 |
| 15–16 | 镜像级健康检查生效、健康历史可读 |
| 17–18 | PID 1 忽略 SIGTERM(137) vs `--init`(143) |
| 19 | `docker diff` 发现漂移 |
| 20 | `system df` 可用 |
| 21–22 | 退出码语义与清理 |

## 8. 生产上线 checklist（本教程全部要点汇总）

| 项 | 章节 |
| --- | --- |
| 镜像：多阶段、非 root、健康检查、小体积 | 18–22 |
| 数据：命名卷、备份、权限 | 12–14 |
| 网络：自定义网络、服务名、不暴露内部端口 | 15–17 |
| 编排：Compose 分层、profiles、secrets、资源限制 | 26–29 |
| 安全：cap-drop、只读根、no-new-privileges | 30 |
| 可观测：日志轮转、指标、事件 | 31 |
| 供应链：digest、扫描、签名、SBOM | 32 |
| 交付：buildx bake、多架构、CI 缓存 | 33 |
| AI：模型外置、GPU 声明、缓存卷、shm | 34–35 |
| 运维：发布/回滚、退出码、信号、排障路径 | 36 |

## 9. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Docker Docs：`docker stop` 信号、`docker diff`、退出码约定、PID 1 行为；OCI 运行时规范 |
| `[r3]` | 实测 | 22/22；发布/回滚容器替换、端口与名称冲突文案、137 vs 143、`docker diff` 输出均为本机实录 |

## 10. 毕业自查

- [ ] 22/22 通过
- [ ] 能独立完成一次发布与回滚
- [ ] 能按六层定位法分析任意容器故障
- [ ] 能默写八个核心排障命令
- [ ] 能解释 137 与 143 的区别及 PID 1 信号问题
- [ ] 能凭报错原文判断故障层
- [ ] 能对着生产 checklist 逐条检查一个项目

## 11. 全教程结束

到这里你已经覆盖：安装认知（00–05）、镜像与容器（06–11）、数据（12–14）、网络（15–17）、构建（18–22）、仓库（23–25）、编排（26–29）、生产与 AI（30–36）。

下一步建议：把任意一个自己的项目按第 18–22 章容器化，再用第 26–29 章的模板编排，最后用 30–36 章加固与交付——这四步走完，Docker 就不再是"会一点"，而是"能落地"。
