# 36 毕业项目与排障手册

## 一句话结论

发布 = 构建带版本标签的镜像 + `compose up -d`（自动替换变更的服务），回滚 = 换回旧 tag 再 `up -d`。排障 80% 的场景靠四样东西定位：**`docker logs`、`docker inspect`、退出码、`docker diff`**。

## 毕业项目

```bash
# 1. 构建两个版本
docker build --build-arg APP_VERSION=v1 -t ch36-app:v1 .
docker build --build-arg APP_VERSION=v2 -t ch36-app:v2 .

# 2. 发布 v1
docker compose --env-file .env.v1 up -d
curl http://127.0.0.1:18096/version      # {"version":"v1",...}

# 3. 发布 v2（容器被替换，不是叠加）
docker compose --env-file .env.v2 up -d

# 4. 回滚
docker compose --env-file .env.v1 up -d
```

## 怎么跑

```powershell
cd "07-生产与AI实战\36-毕业项目与排障手册\examples"
uv run python verify.py
```

## 本机实测（22/22）

| 环节 | 实测 |
| --- | --- |
| 构建 v1/v2 | 成功 |
| 首次发布 | `/version` → `v1` |
| 发布 v2 | 版本切换，**容器 ID 变化**，只剩 1 个容器 |
| 回滚 | `/version` → `v1` |
| 异常退出 | 退出码保留为 3 |
| 崩溃原因 | `docker logs` 里有 `fatal: missing config`，`ExitCode=7` |
| 端口冲突 | 启动失败，报错明确 |
| 容器名冲突 | `container name "/ch36-capstone-app-1" is already in use` |
| 镜像级 HEALTHCHECK | 派生容器同样有健康状态 |
| 健康检查历史 | `.State.Health.Log` 可读 |
| PID 1 是 python | `docker stop` → **137**（SIGTERM 被忽略，10 秒后 SIGKILL） |
| 加 `--init` | `docker stop` → **143**（tini 转发 SIGTERM） |
| `docker diff` | 显示 `A /home/appuser/drift.txt` |
| `docker system df` | 输出含 Images/Containers |

## 发布与回滚的正确做法

| 做法 | 评价 |
| --- | --- |
| `image: app:${VERSION}` + `up -d` | ✅ 推荐，Compose 自动重建 |
| `docker rm -f` + `docker run` | ❌ 手工、易漏参数 |
| 就地 `docker exec` 改代码 | ❌ 漂移，无法复现 |
| `latest` 覆盖推送 | ❌ 无法回滚到确定版本 |
| 每次 tag 用 git sha | ✅ 可追溯 |

发布检查清单：

- [ ] 镜像 tag 不可变（version/sha，不用 latest）
- [ ] 有健康检查，`up -d --wait` 再放流量
- [ ] 有回滚预案（旧 tag 还在仓库）
- [ ] 数据卷与迁移脚本兼容新旧两版（先兼容再加约束）
- [ ] 变更前有备份

## 排障：从现象到根因

```text
容器起不来 / 反复重启
├─ docker logs <容器>              → 应用报错原文
├─ docker inspect -f '{{.State.ExitCode}}'  → 0/1/2=应用退出, 137=OOM/KILL, 143=SIGTERM
├─ docker inspect -f '{{.State.OOMKilled}}' → true 就是内存不够
└─ docker inspect -f '{{.State.Error}}'     → 启动阶段错误（端口/挂载/权限）

能起来但访问不了
├─ docker port <容器>              → 端口映射是否存在
├─ docker inspect -f '{{.State.Health.Status}}' → unhealthy 看 .State.Health.Log
├─ docker exec -it <容器> sh       → 容器内 curl 127.0.0.1
└─ 网络：服务名能否解析、是否同一网络（第 15–17 章）

数据没了
├─ docker volume ls / inspect      → 卷是否存在
├─ docker inspect -f '{{json .Mounts}}' → 挂载点对不对
└─ 是否用了 down -v（第 27 章）

镜像太大 / 构建变慢
├─ docker history <镜像>           → 哪层最大
├─ docker system df -v             → 磁盘占用
└─ 缓存是否命中（第 19、33 章）
```

## 八条命令覆盖 80% 排障

```bash
docker logs -f --tail 200 <容器>                 # ① 应用日志
docker inspect <容器> | jq '.[0].State'          # ② 状态/退出码/OOM
docker exec -it <容器> sh                        # ③ 进容器验证
docker diff <容器>                               # ④ 文件漂移
docker stats --no-stream                         # ⑤ 资源占用
docker events --filter container=<容器>          # ⑥ 实时事件
docker system df -v                              # ⑦ 磁盘分布
docker compose config                            # ⑧ 最终配置
```

## 退出码速查

| 退出码 | 含义 | 处理 |
| --- | --- | --- |
| 0 | 正常结束 | 长驻服务不该出现 |
| 1 | 应用错误 | 看日志 |
| 2 | shell/参数错误 | 检查 CMD/ENTRYPOINT |
| 125 | docker 自身报错（参数/冲突） | 看 docker 报错 |
| 126 | 命令不可执行 | 权限/shebang |
| 127 | 命令不存在 | PATH/镜像缺二进制 |
| 137 | SIGKILL（常见：OOM、stop 超时） | 查 OOMKilled / `--init` |
| 143 | SIGTERM（优雅停止） | 正常 |

**137 与 143 的区别是排障分水岭**：137 说明进程没优雅退出，要么被 OOM 杀，要么忽略信号被强杀。

## PID 1 信号问题（本章实测）

```bash
docker run -d --name app myapp            # python 作为 PID 1
docker stop app                            # 等 10 秒后强杀 → 137
```

原因：容器内 PID 1 对未注册处理函数的信号**不采用默认动作**，SIGTERM 被忽略。

| 解法 | 做法 |
| --- | --- |
| `--init` | tini 作 PID 1，转发信号 → 143 |
| 应用内注册 handler | `signal.signal(SIGTERM, ...)` 后优雅退出 |
| 用带 init 的基础镜像 | `tini`、`dumb-init` |

实测对比：同一镜像不加 `--init` 是 137，加 `--init` 是 143。

## 常见故障速查表

| 现象 | 首要怀疑 | 命令 |
| --- | --- | --- |
| `port is already allocated` | 宿主端口被占 | `docker ps --filter publish=<端口>` |
| `container name is already in use` | 同名容器残留 | `docker ps -a --filter name=` |
| `no space left on device` | 磁盘/日志满 | `docker system df -v`、第 31 章轮转 |
| `permission denied` 挂载 | 宿主目录属主 | 命名卷或 chown |
| `exec format error` | 镜像架构不对 | `docker inspect .Architecture` |
| `Connection refused` | 服务未就绪/端口错 | 健康检查 + 服务名 |
| 容器 `Restarting` 循环 | 启动即崩 | `logs` + `ExitCode` |
| `unhealthy` 但服务正常 | 检查命令错 | `.State.Health.Log` |
| `OOMKilled` | 内存限制太小 | 调大或限堆 |
| 拉取失败 `TLS handshake timeout` | 网络/代理 | 配 daemon 代理（第 05 章） |

## 常用命令总表（速查）

| 类别 | 命令 |
| --- | --- |
| 镜像 | `docker images` / `pull` / `tag` / `rmi` / `save` / `load` / `history` |
| 容器 | `run` / `ps -a` / `start` / `stop` / `restart` / `rm` / `exec` / `cp` / `logs` / `diff` / `top` |
| 数据 | `volume create/ls/inspect/rm/prune`，`-v` / `--mount` |
| 网络 | `network create/ls/inspect/connect/disconnect/prune`，`-p` |
| 构建 | `build` / `buildx build` / `buildx bake` / `build --target` / `--cache-from` |
| 编排 | `compose up/down/ps/logs/exec/config/run/scale/profile` |
| 系统 | `system df` / `system prune -a` / `info` / `version` / `events` |
| 安全 | `scout cves` / `trivy image` / `--cap-drop` / `--read-only` |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 回滚后还是新版本 | 用了 `latest` 或同名 tag | 用不可变 tag |
| `up -d` 没生效 | 配置没变，容器不重建 | `--force-recreate` 或改镜像 tag |
| stop 要等 10 秒 | PID 1 忽略 SIGTERM | `--init` 或注册 handler |
| 数据丢 | `down -v` | 先确认再执行 |
| 改了镜像但容器还是旧的 | 容器用的是旧 image id | `up -d` 或重新 `run` |
| 磁盘满 | 无日志轮转 + 未 prune | 第 11、31 章 |
| 排障时容器已退出 | 无法 `exec` | 用 `logs`/`inspect`，或 `run` 覆盖 entrypoint |
| 以为是网络问题 | 其实是健康检查失败 | 先看 `.State.Health` |

## 毕业标准（全教程）

- [ ] 37 章全部验收通过（00–36）
- [ ] 能独立把任意一个项目容器化并写 Dockerfile
- [ ] 能设计卷/网络/Compose 编排
- [ ] 能做出生产级镜像（多阶段、非 root、健康检查）
- [ ] 能解释镜像仓库、CI/CD、扫描、签名的关系
- [ ] 能配资源限制与安全加固
- [ ] 能搭 AI 应用栈（向量库 + Agent + 工具网关）
- [ ] 遇到容器故障能在 10 分钟内定位到层（应用/镜像/容器/网络/存储/宿主）
