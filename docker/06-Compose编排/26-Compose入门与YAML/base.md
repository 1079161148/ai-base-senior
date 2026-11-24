# 26 Compose 入门与 YAML · 完整版

## 0. 怎么用

跑 23/23。本章只做一件事：把"一长串 docker run"变成"一个 YAML + 三条命令"，并搞清楚 Compose 到底替你做了什么。

## 1. 概念

Compose 是 Docker 官方的**单机多容器编排工具**。它读 `compose.yaml`，把声明翻译成一系列 Docker API 调用。

要先破除一个误解：

> **Compose 不调度、不集群、不做高可用。** 它跑在你本机（或单台服务器）的 dockerd 上，和 `docker run` 是同一层。真要跨机器编排是 K8s 的事。

对比一下同一个项目两种写法：

```bash
# 手敲版
docker network create appnet
docker volume create appdata
docker run -d --name web --network appnet -p 127.0.0.1:18080:80 -v appdata:/data nginx:1.27-alpine
docker run -d --name worker --network appnet --restart unless-stopped -e MODE=demo alpine:3.20 sleep infinity

# Compose 版
docker compose up -d
```

差距不在"少敲几个字"，而在于：**配置可版本化、环境可复制、依赖关系被显式声明、清理是原子的**。

## 2. 机制：up 到底做了什么

```text
docker compose up -d
  ├─ 1. 读取 compose.yaml，做 schema 校验
  ├─ 2. 变量插值（.env / --env-file / shell 环境）
  ├─ 3. 合并 override 文件（compose.override.yaml 自动生效）
  ├─ 4. 计算项目名 → 给资源打标签 com.docker.compose.project
  ├─ 5. 按依赖顺序：创建网络 → 创建卷 → 拉镜像/构建 → 创建容器 → 启动
  └─ 6. 已存在的容器做"差异更新"：配置没变就不动，变了才重建
```

第 6 步是关键：`up` 是**幂等**的，重复执行不会重建没变化的容器。想强制重建用 `--force-recreate`。

所有资源都带标签，所以 `down` 能精确找回自己创建的容器：

```bash
# 本章实测：容器上的标签
docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' ch26-compose-web-1
# ch26-compose
docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' ch26-compose-web-1
# web
```

## 3. YAML 结构逐个拆解

### 3.1 顶层四块

```yaml
name: ch26-file          # ① 项目名
services:                # ② 服务（唯一必填）
  web: { ... }
networks:                # ③ 网络
  default:
    name: ch26-net
volumes:                 # ④ 命名卷
  data:
```

`name`、`networks`、`volumes` 都是可选的；`services` 必须有，且不能为空。

### 3.2 服务定义

最少只要两行：

```yaml
services:
  web:
    image: nginx:1.27-alpine
```

用本地代码构建则是：

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: prod          # 多阶段构建的目标阶段
      args:
        PY_VERSION: "3.12"
```

`image` 与 `build` 可以同时出现：`build` 负责构建，`image` 指定构建出来的名字（`build: .` + `image: myapp:v1` 等价于 `docker build -t myapp:v1 .`）。

### 3.3 变量插值（本机实测）

```yaml
environment:
  GREETING: hello-${COMPOSE_TEST_USER:-guest}
  FALLBACK: ${NOT_SET_ANYWHERE:-guest}
```

`.env`（放在项目目录，或用 `--env-file` 指定）：

```dotenv
COMPOSE_TEST_USER=bob
```

`docker compose config` 渲染结果：

```yaml
environment:
  FALLBACK: guest
  GREETING: hello-bob
```

插值语法：

| 写法 | 含义 |
| --- | --- |
| `${VAR}` | 直接取值，未设置时为空串并告警 |
| `${VAR:-default}` | 未设置或为空 → `default` |
| `${VAR-default}` | 仅未设置 → `default` |
| `${VAR:?err}` | 未设置就**报错退出**（生产必备） |
| `$$` | 转义成字面量 `$` |

`${VAR:?必须设置}` 是最值得记住的一个——把"忘了配环境变量"从运行时故障提前成启动失败。

### 3.4 项目名与命名规则

```text
优先级：-p  >  COMPOSE_PROJECT_NAME  >  顶层 name  >  目录名
```

本章实测：文件里写 `name: ch26-file`，命令行加 `-p ch26-compose`，`config` 输出 `name: ch26-compose`——**命令行赢**。

派生命名：

| 资源 | 规则 | 本章实例 |
| --- | --- | --- |
| 容器 | `{项目}-{服务}-{序号}` | `ch26-compose-web-1` |
| 默认网络 | `{项目}_default` | 显式指定为 `ch26-net` |
| 命名卷 | `{项目}_{卷名}` | `ch26-compose_data` |

默认网络名里的 `_default` 是很多人"找不到网络"的原因。

## 4. config：排查配置的第一选择

`docker compose config` 输出的是**合并 + 插值后的最终结果**，不是原文件。任何"我明明写了却不生效"的问题，第一步都是它。

本章实测的归一化细节：

| 原写法 | `config` 输出 |
| --- | --- |
| `ports: ["127.0.0.1:18080:80"]` | `{mode: ingress, host_ip: 127.0.0.1, target: 80, published: "18080", protocol: tcp}` |
| `depends_on: [web]` | `web: {condition: service_started, required: true}` |
| `volumes: [data:/data]` | `{type: volume, source: data, target: /data, volume: {}}` |
| `volumes: {data: {}}` | `data: {name: ch26-compose_data}` |

几个高频用法：

```bash
docker compose config -q                  # 只校验（CI 门禁）
docker compose config --services          # 服务名清单
docker compose config --volumes           # 卷清单
docker compose config --profiles          # profile 清单（第 29 章）
docker compose config --format json       # 交给 jq 处理
```

校验能力实测——依赖不存在的服务时，启动前就被拦下：

```text
service "api" depends on undefined service "db": invalid compose project
```

**所以 CI 里永远先跑 `config -q`，别等 `up` 才发现拼写错误。**

## 5. 命令全景

| 类别 | 命令 | 说明 |
| --- | --- | --- |
| 生命周期 | `up -d` | 创建并启动 |
| | `up -d --build` | 先重建镜像 |
| | `up -d --force-recreate` | 无视配置差异强制重建 |
| | `down` | 停 + 删容器/网络 |
| | `down -v` | 连命名卷删（**数据会丢**） |
| | `down --rmi local` | 连本章构建的镜像删 |
| | `start` / `stop` / `restart` | 不重建，只改运行状态 |
| 观察 | `ps` / `ps -a` | 状态 |
| | `ps --format json` | 给脚本用 |
| | `logs -f --tail 100 <svc>` | 日志 |
| | `top <svc>` | 容器内进程 |
| | `events` | 实时事件流 |
| 交互 | `exec <svc> sh` | 进运行中的容器 |
| | `exec -T <svc> cmd` | 无 TTY（脚本用） |
| | `run --rm <svc> cmd` | 一次性容器，不占端口 |
| | `cp <svc>:/path ./` | 拷文件 |
| 构建 | `build` / `build --no-cache` | 构建 |
| | `pull` / `push` | 拉/推 |
| 诊断 | `config` | 渲染终态 |
| | `images` | 本项目用到的镜像 |
| | `port <svc> 80` | 查映射端口 |
| | `ls -a` | 全部项目 |

最常用的五个背下来就够日常：`up -d`、`ps`、`logs -f`、`exec`、`down`。

## 6. 边界条件与坑

| 现象 | 根因 | 处理 |
| --- | --- | --- |
| `invalid project name` | 目录名含中文/大写/特殊字符 | `name:` 或 `-p` 显式指定 |
| 改 `.env` 无效 | 插值发生在启动时 | 重新 `up -d` |
| `up` 后立刻 `Exited` | 主进程结束容器就结束 | 用前台常驻进程 |
| 端口冲突 | 宿主机已占用 | 换端口 / 绑 `127.0.0.1:` |
| 数据"消失" | 项目名变了 → 卷名变了 | 卷写 `name:` 或 `external: true` |
| 依赖顺序没生效 | `depends_on` 只管启动顺序不管就绪 | 第 28 章 `condition: service_healthy` |
| 改了源码容器没变 | 代码在镜像里，不在卷里 | `--build` 或开发用 bind mount |
| `container_name` 后不能 `--scale` | 名字必须唯一 | 删掉 `container_name` |
| YAML 报错 `found character '\t'` | 用了 Tab | 改空格 |
| `down` 后卷还在 | 默认不删卷（防误删数据） | 确认后 `down -v` |

## 7. 最佳实践

1. **文件命名**：`compose.yaml`（官方推荐，`docker-compose.yml` 仍兼容）。
2. **必写 `name:`**：目录名不可控时（CI 检出路径随机）项目名会乱。
3. **不用 `version:`**：v2 起废弃，本机 v5.3.1 会告警。
4. **端口绑 `127.0.0.1:`**：本地开发不要暴露到局域网。
5. **`environment` 用字典不用列表**：可读性更好，diff 更清晰。
6. **密钥走 `secrets` 或外部 `.env`**：不要把密码写进 YAML 提交（第 29 章）。
7. **`config -q` 进 CI**：零成本的语法门禁。
8. **`down -v` 要谨慎**：它会删数据卷，生产环境禁止随手执行。
9. **一个项目一个目录**：Compose 靠目录推导项目名，混放会互相干扰。

## 8. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Compose Specification、`docker compose config` 参考 |
| `[r3]` | 实测 | 23/23；`version` 废弃告警、`-p` 覆盖 `name`、`.env` 插值、非法依赖拦截均为本机实录 |

## 9. 毕业自查

- [ ] 23/23 通过
- [ ] 能徒手写出一个两服务的 `compose.yaml`
- [ ] 能解释 `up -d` 为什么是幂等的
- [ ] 能说出项目名的 4 级优先级与三类派生命名
- [ ] 知道 `config` / `config -q` / `config --services` 各自的用途
- [ ] 知道 `down` 与 `down -v` 的区别和风险

## 10. 下一章

第 27 章用 Compose 编一个真实三层应用：Web + PostgreSQL + Redis，含初始化 SQL、密码注入、跨服务 DNS 寻址与数据持久化。
