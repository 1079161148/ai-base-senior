# 29 Compose 生产实践 · 完整版

## 0. 怎么用

跑 26/26。本章把"能跑起来"升级成"能上生产"：配置分层、可选服务、密钥隔离、资源上限、多副本。每一条都用真实 `docker inspect` 结果验证，不靠文档推断。

## 1. 从"一个文件"到"一套结构"

开发阶段的 `compose.yaml` 通常有三个问题：把所有服务塞在一起、密码明文写在 YAML 里、生产参数靠手工改。生产化的目标是让**差异只在差异文件里**：

```text
compose.yaml              入口：name、include、公共配置
compose.override.yaml     本地开发差异（默认自动加载）
compose.prod.yaml         生产差异（显式 -f 叠加）
compose.include.yaml      按域拆出去的服务
base-service.yaml         extends 复用的服务片段
secrets/db_password.txt   密钥文件（.gitignore 掉）
*.env                     环境变量（敏感值不进仓库）
```

本章的目录就是这套结构的可运行示例。

## 2. profiles：可选服务

### 2.1 语义

```yaml
services:
  api:      {}                  # 无 profile → 永远启动
  migrate:  { profiles: ["tools"] }
  pgadmin:  { profiles: ["debug"] }
```

| 命令 | 实际启动 |
| --- | --- |
| `up -d` | `api` |
| `up -d --profile tools` | `api` + `migrate` |
| `up -d --profile debug` | `api` + `pgadmin` |
| `up -d --profile "*"` | 全部 |

### 2.2 本章实测

| 断言 | 结果 |
| --- | --- |
| `config --services` | `api`、`extended`、`metrics`、`web`——**不含** `shell`/`migrate` |
| `config --profiles` | `tools` |
| `up -d` 后 | `shell` 容器不存在 |
| `--profile tools up -d migrate` | 执行完，日志 `migrated` |

### 2.3 容易忽略的两点

1. **profile 服务对 `config --services` 不可见**，所以脚本里想枚举全部服务要用 `--profile "*"`。
2. **清理也要带 profile**：本章第一次验收就踩到了——`down -v` 之后 `ps -aq` 仍剩 1 个 `migrate` 容器。加 `--profile tools down -v --remove-orphans` 才干净。

## 3. 多文件叠加

### 3.1 自动加载的真实规则（实测）

| 调用 | 是否合并 `compose.override.yaml` |
| --- | --- |
| `docker compose config`（默认发现 `compose.yaml`） | **是** |
| `docker compose -f compose.yaml config` | **否** |

本章两次 `config` 的输出对比：

```text
默认发现：     APP_MODE: local / OVERRIDE_MARK: from-override
显式 -f：      APP_MODE: local /（没有 OVERRIDE_MARK）
```

这条是本章最有价值的实测结论之一——网上大量教程默认"`-f` 也会带 override"，实际不会。

### 3.2 合并语义

| 类型 | 例子 | 规则 |
| --- | --- | --- |
| 标量 | `image`、`command`、`restart` | 后者替换 |
| 映射 | `environment`、`labels`、`deploy.resources` | 按键合并，后者赢 |
| 序列 | `ports`、`volumes`、`dns` | **追加** |

序列追加导致的经典事故：

```yaml
# compose.yaml
ports: ["18080:80"]
# compose.prod.yaml
ports: ["18080:80"]     # 你以为覆盖，实际变成两条相同映射 → 冲突
```

正确做法：生产文件里**不要重复写**序列字段；真要替换就统一只写一处。

本章实测的映射合并：memory 在基础文件是 `64M`，`-f compose.prod.yaml` 叠加后 `config` 显示 `"134217728"`（128M）。

### 3.3 命名与约定

| 文件 | 用途 | 是否自动加载 |
| --- | --- | --- |
| `compose.yaml` | 基础 | 是（默认发现） |
| `compose.override.yaml` | 本地开发 | 仅默认发现时 |
| `compose.prod.yaml` | 生产 | 否，需 `-f` |
| `compose.test.yaml` | 测试 | 否，需 `-f` |

## 4. secrets：密钥的正确姿势

### 4.1 声明与使用

```yaml
services:
  api:
    secrets:
      - db_password
      - source: tls_cert
        target: server.crt        # 可改容器内文件名
        mode: 0400                # swarm 下有效
secrets:
  db_password:
    file: ./secrets/db_password.txt
  tls_cert:
    external: true                # 由外部（swarm/k8s）提供
```

容器内路径：`/run/secrets/<name>`（或自定义 `target`）。

本章实测：

| 检查 | 结果 |
| --- | --- |
| `cat /run/secrets/db_password` | `s3cr3t-from-file-29`（与文件一致） |
| `docker inspect .Config.Env` | 不含密钥明文 |
| `.Mounts` | `/run/secrets/db_password`，`RW=false` |

### 4.2 secrets vs environment vs build ARG

| 维度 | environment | build ARG | secrets |
| --- | --- | --- | --- |
| `docker inspect` 可见 | 是 | 镜像历史可见 | 否 |
| 子进程继承 | 是 | — | 否（要显式读文件） |
| 进入镜像层 | 否 | **是**（`docker history` 可见） | 否 |
| 适合 | 非敏感配置 | 构建期参数（非密钥） | 密码、令牌、证书 |

**永远不要把密钥写成 `ENV`/`ARG` 打进镜像**——层里的值删不掉（第 20 章的"幽灵数据"同源）。

### 4.3 局限

Compose 的 secrets 本质是 **bind mount + 权限**，没有加密、没有轮换、没有审计。生产级的密钥管理要么用 Swarm secrets（加密存储）、要么用 Vault/AWS Secrets Manager + 启动时注入、要么上 K8s Secret + External Secrets Operator。

## 5. extends 与 include

### 5.1 extends

```yaml
# base-service.yaml
services:
  alpinebase:
    image: alpine:3.20
    command: ["sh", "-c", "sleep infinity"]
    environment:
      BASE_KEY: base-value

# compose.yaml
services:
  extended:
    extends:
      file: base-service.yaml
      service: alpinebase
    environment:
      CHILD_KEY: child-value
```

实测 `config` 结果同时包含 `BASE_KEY: base-value` 与 `CHILD_KEY: child-value`——映射按键合并。

用途：统一 `logging`、`healthcheck`、`ulimits`、`security_opt` 这类重复配置。

限制：

- 只能继承**服务**，不能继承顶层 `volumes`/`networks`；
- 相对路径（`build.context`、`volumes` 的 `./`）以**被引用文件**所在目录为基准；
- 跨平台/跨仓库共享时容易踩路径坑，推荐 `include`。

### 5.2 include

```yaml
include:
  - compose.include.yaml
  - path: ../shared/monitor.yaml
    env_file: ../shared/.env
```

实测：`metrics` 服务被合并，`config --services` 有它，`up -d` 后容器真实运行（`ch29-prod-metrics-1`）。

`include` 与 `extends` 的取舍：

| 场景 | 选择 |
| --- | --- |
| 一套健康检查给 10 个服务用 | `extends` |
| 按域拆文件（db/web/monitor） | `include` |
| 跨项目复用一组服务 | `include`（支持相对路径与 env_file） |
| 只想覆盖几个字段 | 多 `-f` 叠加 |

## 6. 资源限制

### 6.1 写法与实测映射

```yaml
deploy:
  resources:
    limits:
      cpus: "0.50"
      memory: 64M
    reservations:
      cpus: "0.25"
      memory: 32M
```

| 字段 | `docker inspect` | 实测值 |
| --- | --- | --- |
| `cpus: "0.50"` | `.HostConfig.NanoCpus` | `500000000` |
| `memory: 64M` | `.HostConfig.Memory` | `67108864` |

结论：**`docker compose` 会把 `deploy.resources.limits` 翻译成 `--cpus` / `--memory`**，非 swarm 模式同样生效。

### 6.2 与 `deploy.replicas` 的区别

| 字段 | 非 swarm（docker compose） | swarm |
| --- | --- | --- |
| `resources.limits` | **生效** | 生效 |
| `replicas` | **被忽略** | 生效 |
| `restart_policy` | 被忽略（用服务级 `restart`） | 生效 |

所以单机多副本只能靠 `--scale`。

### 6.3 内存限制的后果

`memory: 64M` 是**硬限制**，超了内核直接 OOMKill：

```bash
docker inspect -f '{{.State.OOMKilled}}' <容器>   # true 即被杀
docker inspect -f '{{.HostConfig.Memory}}' <容器>
```

Java/Node 这类运行时还要额外限制堆大小（`-Xmx`、`--max-old-space-size`），否则容器被限制而运行时不知道，仍然会按宿主机内存申请。

### 6.4 其它常用限制

```yaml
pids_limit: 200              # 防 fork 炸弹
ulimits:
  nofile: { soft: 65536, hard: 65536 }
read_only: true              # 只读根文件系统（第 22 章）
tmpfs: ["/tmp"]
security_opt: ["no-new-privileges:true"]
cap_drop: ["ALL"]
```

## 7. --scale 与多副本

```bash
docker compose up -d --scale web=3
docker compose ps -q web | wc -l     # 3
```

前提条件（本章实测均满足）：

| 条件 | 说明 |
| --- | --- |
| 不写 `container_name` | 名字必须由 Compose 生成 |
| 不写固定宿主端口 | 用 `expose` 或端口段 `18080-18082:80` |
| 前面有反代 | 否则 3 个副本没人分发流量 |

多副本的流量分发方案：

| 方案 | 说明 |
| --- | --- |
| Nginx/Traefik 反代 + Docker DNS | 反代解析服务名，Docker 内置 DNS 轮询 |
| Swarm/K8s | 原生 Service/Ingress |
| 固定端口段 + 外部 LB | 简单粗暴，维护成本高 |

注意：**Docker 内置 DNS 对多副本是轮询，不做健康感知**。要让流量避开 `unhealthy` 副本，得靠反代的主动健康检查或编排平台。

## 8. 逐条验收解读（26 条）

| 组 | 覆盖内容 |
| --- | --- |
| 1–4 | `config -q`、include 合并、profile 可见性、`--profiles` |
| 5–6 | override 自动合并的真实规则（默认发现 vs `-f`） |
| 7–8 | env_file 覆盖顺序、前者不丢失 |
| 9 | extends 字段合并 |
| 10–12 | 多 `-f` 覆盖环境变量与资源、`config --format json` 可编程处理 |
| 13–14 | 默认服务集启动、include 服务真实运行、profile 服务未启动 |
| 15–17 | secrets 可读、不泄漏到 env、只读挂载 |
| 18–19 | limits 的 memory/cpus 真实落到 HostConfig |
| 20–22 | `--scale` 生效、副本数、独立 IP |
| 23–25 | `--profile` 拉起一次性任务、任务真实执行 |
| 26 | 带 profile 的彻底清理 |

## 9. 坑与对策

| 现象 | 根因 | 对策 |
| --- | --- | --- |
| override 不生效 | `-f` 关闭自动发现 | 显式 `-f compose.override.yaml` |
| 端口重复映射报错 | 序列是追加语义 | 生产文件不重复写序列字段 |
| profile 服务没起来 | 未加 `--profile` | 加参数，或把长期服务去掉 profile |
| 残留容器 | 一次性任务在 profile 里 | `--profile tools down --remove-orphans` |
| secret 路径错 | 默认 `/run/secrets/<name>` | 写 `target` |
| 密钥进镜像 | 用了 `ENV`/`ARG` | 改 `secrets`，重建镜像 |
| limits 不生效 | 写在了 `deploy.resources.limits` 之外 | 确认层级，用 `inspect` 复核 |
| 容器 OOMKilled | 硬限制太小 / 运行时不知道上限 | 调大 + 限制堆 |
| `--scale` 端口冲突 | 固定宿主端口 | `expose` 或端口段 |
| `--scale` 名字冲突 | `container_name` | 删掉 |
| 多副本无流量分发 | 没有反代 | 加 Nginx/Traefik 或上编排平台 |

## 10. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Compose Specification：profiles / include / extends / secrets / deploy.resources；Docker Docs「Merge Compose files」 |
| `[r3]` | 实测 | 26/26；`-f` 与 override 的关系、序列追加语义、limits 落成 NanoCpus/Memory、profile 清理残留均为本机实录 |

## 11. 毕业自查

- [ ] 26/26 通过
- [ ] 能画出自己的多文件结构并为每个文件说出用途
- [ ] 能背出三类合并语义
- [ ] 能解释 `-f` 与 override 自动加载的关系
- [ ] 能解释 `extends` 与 `include` 的适用边界
- [ ] 能说明 secrets 相对 environment 的三个优势与两个局限
- [ ] 能说明 `--scale` 的三个前提
- [ ] 能区分 `deploy.resources.limits` 与 `deploy.replicas` 在非 swarm 下的行为

## 12. 下一章

M06 完成。第 30 章进入 M07 生产与 AI 场景：运行时安全加固（capabilities、只读根、seccomp、非 root）与资源治理。
