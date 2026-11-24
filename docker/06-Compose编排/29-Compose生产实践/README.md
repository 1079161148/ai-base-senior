# 29 Compose 生产实践

## 一句话结论

生产用的 Compose 文件不是"一个 YAML 写完"，而是**分层**：基础文件 + 环境叠加（`-f` 多文件）、可选服务（`profiles`）、密钥（`secrets`）、公共片段（`extends`/`include`）、资源上限（`deploy.resources.limits`）。

## 最小可运行案例

```yaml
services:
  api:
    image: myapp:1.4.2
    env_file: [base.env, local.env]      # 后者覆盖前者
    secrets: [db_password]               # → /run/secrets/db_password
    deploy:
      resources:
        limits: { cpus: "0.50", memory: 64M }
  shell:
    image: alpine:3.20
    profiles: ["tools"]                  # 默认不启动
secrets:
  db_password:
    file: ./secrets/db_password.txt
```

```bash
docker compose up -d                              # 默认服务集
docker compose --profile tools up -d migrate      # 额外拉起工具类服务
docker compose -f compose.yaml -f compose.prod.yaml up -d   # 生产叠加
```

## 怎么跑

```powershell
cd "06-Compose编排\29-Compose生产实践\examples"
uv run python verify.py
```

## 本机实测（26/26）

| 能力 | 实测结果 |
| --- | --- |
| `include` | `metrics` 出现在 `config --services` 并且真实运行 |
| `profiles` | profile 服务默认不在 `--services` 中；`config --profiles` → `tools` |
| `compose.override.yaml` | **默认发现时**自动合并（`OVERRIDE_MARK: from-override`） |
| 显式 `-f compose.yaml` | override **不**自动合并（`OVERRIDE_MARK` 不存在） |
| `env_file` 多文件 | `APP_MODE=local`（后者赢），`DB_HOST=db` 保留 |
| `extends` | `BASE_KEY` 继承 + `CHILD_KEY` 自身 |
| 多 `-f` 叠加 | `DEPLOY_ENV=prod`，`memory: 134217728`（覆盖 64M） |
| `secrets` | `/run/secrets/db_password` 可读，内容与文件一致 |
| 密钥是否泄漏到环境变量 | 否 |
| secret 挂载 | `RW=false` |
| `deploy.resources.limits.memory` | `HostConfig.Memory = 67108864` |
| `deploy.resources.limits.cpus` | `HostConfig.NanoCpus = 500000000` |
| `--scale web=3` | 3 个副本，IP 互不相同 |
| `--profile tools up -d migrate` | 执行完输出 `migrated` |
| 清理 | 必须带 `--profile tools` 才能把一次性任务一起删 |

## 生产化能力逐项

### 1. profiles：把"可选服务"从默认启动里摘出去

```yaml
services:
  migrate:   { profiles: ["tools"] }
  seed:      { profiles: ["tools"] }
  pgadmin:   { profiles: ["debug"] }
  api:       { }                       # 无 profile = 永远启动
```

| 命令 | 启动范围 |
| --- | --- |
| `docker compose up -d` | 只有无 profile 的服务 |
| `--profile tools up -d` | 无 profile + tools |
| `--profile tools --profile debug up -d` | 前者 + debug |
| `--profile "*"` | 全部 |

规则细节：

- 有 profile 的服务**默认不可见**：`config --services` 不列它；
- 一旦某个服务被启动，它的依赖（即使有别的 profile）也会被带上；
- 清理时也要带 profile：`--profile tools down -v`。

### 2. 多文件叠加：开发/生产差异只写差异部分

```bash
docker compose -f compose.yaml -f compose.override.yaml up -d   # 本地
docker compose -f compose.yaml -f compose.prod.yaml up -d       # 生产
```

合并规则（Compose Specification）：

| 类型 | 行为 |
| --- | --- |
| 标量（`image`、`command`） | 后者**替换**前者 |
| 映射（`environment`、`labels`） | **按键合并**，冲突时后者赢 |
| 序列（`ports`、`volumes`） | **追加**（不是替换），注意重复端口冲突 |
| `deploy.resources` | 按键合并 |

结合本章实测：`compose.yaml` 里 memory 是 `64M`，用 `-f compose.prod.yaml` 叠加后变成 `128M`。

**override 自动加载的真实规则**（本章实测）：

| 调用方式 | 是否自动加载 `compose.override.yaml` |
| --- | --- |
| `docker compose up`（默认发现 `compose.yaml`） | 是 |
| `docker compose -f compose.yaml up` | **否** |

很多人以为写 `-f` 也会带 override，结果环境变量没生效。想叠加就显式写全。

### 3. secrets：密钥不以环境变量传递

```yaml
services:
  api:
    secrets: [db_password]
secrets:
  db_password:
    file: ./secrets/db_password.txt
    # 或用外部已有密钥：external: true
```

容器内：

```bash
cat /run/secrets/db_password      # s3cr3t-from-file-29
```

对比环境变量的劣势：

| 维度 | `environment` | `secrets` |
| --- | --- | --- |
| 可见性 | `docker inspect` 明文 | 文件挂载，inspect 看不到内容 |
| 子进程 | 自动继承，容易打印到日志 | 需显式读取 |
| 镜像层 | 误 `ARG`/`ENV` 会写进镜像 | 不进镜像 |
| 权限 | — | 只读挂载（`RW=false`），默认 0444 |

注意：**Compose 的 secrets 只是"文件挂载 + 权限管理"，没有加密。** 真要加密/轮换，用 Vault、KMS、K8s Secret 或 Docker Swarm secrets。

### 4. extends 与 include 的区别

| 特性 | `extends` | `include` |
| --- | --- | --- |
| 作用 | **单个服务**继承另一份定义 | **整个文件**的服务合并进来 |
| 写法 | 服务里写 `extends: {file, service}` | 顶层写 `include: [file]` |
| 覆盖 | 子级字段覆盖父级 | 各服务平级合并 |
| 常见用途 | 多个服务共享一套 `logging`/`healthcheck` | 按域拆分文件（db.yaml、web.yaml） |
| 版本 | 老牌能力 | Compose 2.20+（本机 v5 支持） |

拆分建议：

```text
compose.yaml            主入口（只放 name/include/少量覆盖）
compose.db.yaml         数据库组
compose.web.yaml        应用组
compose.monitor.yaml    监控组（profiles: [monitor]）
compose.prod.yaml       生产差异
```

### 5. 资源限制：deploy.resources.limits 在非 swarm 下也生效

```yaml
deploy:
  resources:
    limits:
      cpus: "0.50"        # 50% 一个核
      memory: 64M         # 硬上限，超了 OOMKilled
    reservations:
      cpus: "0.25"
      memory: 32M
```

实测映射结果：

| YAML | `docker inspect` 字段 | 值 |
| --- | --- | --- |
| `cpus: "0.50"` | `HostConfig.NanoCpus` | `500000000` |
| `memory: 64M` | `HostConfig.Memory` | `67108864` |

`docker compose` 会把 `deploy.resources.limits` 翻译成 `docker run --cpus/--memory`，所以**不用 swarm 也生效**。这是它和 `deploy.replicas`（非 swarm 下不生效）的重要差别。

### 6. --scale：多副本的前提是"不占固定宿主端口"

```bash
docker compose up -d --scale web=3
```

本章 `web` 只写 `expose: ["80"]`，不写 `ports`，因此可以起 3 个副本（`ch29-prod-web-1/2/3`），互不冲突，各自独立 IP。

| 写法 | 能否 `--scale` |
| --- | --- |
| `expose: ["80"]` | 能 |
| `ports: ["18080:80"]` | **不能**（端口冲突） |
| `ports: ["18080-18082:80"]` | 能（端口段按副本分配） |
| `container_name: xxx` | **不能**（名字唯一） |

多副本后前面必须有反代/网关做负载均衡（Nginx、Traefik、Caddy），或者交给 K8s。

## 常用命令

```bash
docker compose config --profiles                 # 有哪些 profile
docker compose --profile "*" config --services   # 全部服务
docker compose --profile tools up -d             # 带工具服务启动
docker compose -f compose.yaml -f compose.prod.yaml config   # 先看合并结果
docker compose up -d --scale web=3
docker compose --profile tools down -v --remove-orphans
docker compose ps --format json | jq '.[] | {Service,State,Health}'
```

**习惯：任何 `-f` 叠加或 profile 变更，先 `config` 看一眼，再 `up`。**

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| override 没生效 | 用了 `-f`，不再自动加载 | 显式 `-f compose.override.yaml` |
| profile 服务起不来 | 忘了带 `--profile` | `--profile tools up -d` |
| `down` 后还有容器残留 | 一次性任务属于某 profile | `--profile tools down --remove-orphans` |
| `ports` 重复且被追加 | 序列是追加语义 | 生产文件里只写差异、不重复端口 |
| `--scale` 报端口冲突 | 固定了宿主端口 | 改 `expose` 或端口段 |
| `--scale` 报名字冲突 | 写了 `container_name` | 删掉 |
| secret 读不到 | 路径不是 `/run/secrets/<name>` | 显式 `target` |
| secret 权限过大 | 默认 0444 | 用 `mode: 0400`（swarm）或应用内校验 |
| 设了 limits 后容器频繁 OOMKilled | 上限太小 | 看 `docker inspect .State.OOMKilled`，调大 |
| 以为 `deploy.replicas` 生效 | 非 swarm 下被忽略 | 用 `--scale` 或上 swarm/K8s |

## 生产检查清单

- [ ] 密钥走 `secrets`/外部注入，仓库里没有明文
- [ ] 有 `compose.prod.yaml`，且 `config` 验证过合并结果
- [ ] 所有长期服务配 `restart: unless-stopped`
- [ ] 关键服务有 `healthcheck`
- [ ] 每个服务有 `deploy.resources.limits`
- [ ] 数据库不发布宿主端口
- [ ] 日志驱动与轮转已配置（第 31 章）
- [ ] 镜像用 digest 或不可变 tag，不用 `latest`
- [ ] 一次性任务放 `profiles`
- [ ] 有 `down -v` 之外的数据备份方案

## 毕业自查

- [ ] 26/26 通过
- [ ] 能解释 `-f` 与 override 自动加载的关系
- [ ] 能说出标量/映射/序列三类合并语义
- [ ] 能说出 `extends` 与 `include` 的区别
- [ ] 能解释为什么 `--scale` 不能配固定宿主机端口
- [ ] 知道 `deploy.resources.limits` 与 `deploy.replicas` 在非 swarm 下的差异
- [ ] 能独立把一套开发用 compose 改造成可上生产的分层结构
