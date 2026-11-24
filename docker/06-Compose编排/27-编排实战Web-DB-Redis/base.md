# 27 编排实战：Web + PostgreSQL + Redis · 完整版

## 0. 怎么用

跑 25/25。这一章是 M06 的主体：把第 12–17 章的卷与网络、第 21–22 章的构建规范，全部落到一个能跑起来的三层应用上。

## 1. 要解决的问题

单机跑三层应用的原始成本：

| 环节 | 手敲 docker run 的复杂度 |
| --- | --- |
| 建网络 | 记名字、每个容器都要 `--network` |
| 建卷 | 记得挂 `/var/lib/postgresql/data` |
| 密码 | `-e POSTGRES_PASSWORD=...` 暴露在 shell history |
| 初始化 SQL | 进容器手工 `psql -f` |
| 启动顺序 | 自己 sleep 等数据库 |
| 清理 | 逐个 `rm -f`，容易漏 |

Compose 把这六件事全部声明化。本章的验收就是逐条证明它们**真的**生效，而不是"配置文件看起来对"。

## 2. 架构

```text
宿主机 127.0.0.1:18081
        │
        ▼
┌─────────────────── ch27-net（自定义 bridge，内置 DNS）───────────────────┐
│                                                                          │
│   api (python:3.12-slim)          db (postgres:16-alpine)                │
│   /app/app.py  ──TCP:5432──►      /var/lib/postgresql/data ◄── pgdata 卷  │
│        │                          /docker-entrypoint-initdb.d ← ./initdb  │
│        └──────TCP:6379──► redis (redis:7-alpine)                          │
│                                  /data ◄── redisdata 卷                   │
└──────────────────────────────────────────────────────────────────────────┘
```

三个服务的任务分工：

| 服务 | 为什么选这个镜像 | 教学点 |
| --- | --- | --- |
| `db` | `postgres:16-alpine`，体积小 | 命名卷、initdb、健康检查 |
| `redis` | `redis:7-alpine` | 内存服务的持久化边界 |
| `api` | `python:3.12-slim` | 服务名寻址、绑定挂载开发流 |

`api` 故意**只用标准库**（`socket` + `http.server`），这样：

1. 不需要 `pip install`，离线可跑；
2. 证明容器间通信就是普通 TCP，没有魔法；
3. 后面换成 FastAPI 只是把 `app.py` 换掉，编排不变。

## 3. 核心机制逐个拆解

### 3.1 服务名 = DNS 主机名

Compose 为每个服务在同一网络上注册网络别名。实测：

```bash
docker compose exec -T api python -c "import socket;print(socket.gethostbyname('db'))"
# 172.19.0.2  ← 与 docker inspect db 在 ch27-net 上的 IP 完全一致
```

三种写法都通，且指向同一容器：

| 写法 | 说明 |
| --- | --- |
| `db` | 服务名（推荐） |
| `db:5432` | 明确端口 |
| 容器 IP | **不推荐**，重建就变 |

服务名解析由 `127.0.0.11` 内置 DNS 完成（第 16 章），**只在自定义网络上生效**。默认 `bridge` 网络没有名称解析，`--network host` 直接共享宿主网络栈。

### 3.2 密码用 `:?` 语法强制注入

```yaml
POSTGRES_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD 未设置}
```

实测（`--env-file env.empty`）：

```text
required variable DB_PASSWORD is missing a value: DB_PASSWORD 未设置
```

对比两种失败方式：

| 做法 | 没配密码时的结果 |
| --- | --- |
| `POSTGRES_PASSWORD: ${DB_PASSWORD}` | 空字符串，容器启动后认证全部失败，**排查半天** |
| `POSTGRES_PASSWORD: ${DB_PASSWORD:?}` | `compose up` 立刻失败，错误信息直接点名变量 |

这是本章最值得带走的一条：**把配置错误提前到启动前**。

### 3.3 initdb：只跑一次

`postgres` 镜像的 `docker-entrypoint.sh` 逻辑：

```text
if PGDATA 目录为空:
    初始化数据库集群
    按字典序执行 /docker-entrypoint-initdb.d/*.{sh,sql,sql.gz}
else:
    跳过初始化，直接启动
```

实测证据链：

| 步骤 | 结果 |
| --- | --- |
| 首次 `up` 后查询 `articles` | 2 行（脚本插入的 2 条） |
| 手工 `INSERT` | 3 行 |
| `compose down`（不删卷）→ `up` | 仍 3 行，**没有回到 2 行** |

如果没有这层"空目录才执行"的保护，每次重启都会重复插入，数据早就乱了。

推论：

- 改了 `01-init.sql` 想重跑 → 必须 `down -v`，或进库手工执行；
- 生产不要用 initdb 做数据库迁移，用 Flyway/Liquibase/Alembic。

### 3.4 卷的生命周期

| 操作 | 容器 | 网络 | 命名卷 |
| --- | --- | --- | --- |
| `stop` / `start` | 保留 | 保留 | 保留 |
| `restart` | 保留（重启进程） | 保留 | 保留 |
| `down` | 删除 | 删除 | **保留** |
| `down -v` | 删除 | 删除 | **删除** |

默认不删卷是安全设计：数据比编排配置重要得多。本章实测 `down` 之后 `ch27-app_pgdata` 依然存在。

### 3.5 Redis 的持久化边界

`redis:7-alpine` 默认开 RDB（快照），触发条件写在镜像内置配置里。本章显式加 `--save 60 1`（60 秒内至少 1 次写就落盘），验收时手工 `SAVE` 再 `restart`：

```bash
docker compose exec -T redis redis-cli SET chapter ch27
docker compose exec -T redis redis-cli SAVE
docker compose restart redis
docker compose exec -T redis redis-cli GET chapter   # → ch27
```

要点：

- **没有 `/data` 卷，`restart` 就丢数据**——容器可写层随容器删除；
- RDB 有丢秒级数据的风险，要更强一致用 AOF（`--appendonly yes`）；
- Redis 当纯缓存时可以不持久化，但要接受"重启后缓存全空"。

## 4. 逐条验收解读（25 条）

| # | 断言 | 证明了什么 |
| --- | --- | --- |
| 1–2 | `config -q`、服务清单 | 配置语法 + 结构正确 |
| 3 | 空环境变量失败 | `:?` 生效 |
| 4 | `up -d` 成功 | 编排可执行 |
| 5–6 | db/redis `healthy` | 健康检查真的在跑 |
| 7 | api 运行中 | 依赖满足后才启动 |
| 8 | `articles` 2 行 | initdb 执行且仅一次 |
| 9 | 3 个列存在 | SQL 脚本结构正确 |
| 10–11 | 两次请求 hits 1→2 | api↔redis 真实联通 |
| 12 | `"db":"up"` | api↔db 真实联通 |
| 13 | 服务名解析 IP 一致 | 内置 DNS 生效 |
| 14–15 | 网络 3 容器、IP 互异 | 网络拓扑正确 |
| 16–17 | 写入后 3 行 | 可写 |
| 18–20 | `down` 后卷在、`up` 后 3 行 | 持久化有效、initdb 未重跑 |
| 21–23 | Redis SET/SAVE/restart/GET | 卷 + RDB 有效 |
| 24–25 | `down -v` 删卷 | 清理语义明确 |

## 5. 常用命令补充

```bash
# 只看某个服务的日志并带时间戳
docker compose logs -f --tail 200 --timestamps api

# 在一次性容器里跑迁移脚本（不占用长期服务）
docker compose run --rm api python migrate.py

# 查看某服务最终生效的环境变量
docker compose exec -T api env | sort

# 导出当前数据库（备份）
docker compose exec -T db pg_dump -U app appdb > backup.sql

# 恢复
docker compose exec -T db psql -U app -d appdb < backup.sql

# 查看服务端口映射
docker compose port api 8000

# 只看资源占用
docker stats $(docker compose ps -q)
```

## 6. 坑与对策

| 现象 | 根因 | 对策 |
| --- | --- | --- |
| 改 init SQL 无效 | PGDATA 非空 | `down -v` / 手工执行 |
| 改密码无效 | 初始化时写入 | `ALTER USER` 或重建卷 |
| `Connection refused` 日志刷屏 | 应用启动快于数据库 | `service_healthy` + 应用侧重试 |
| 数据库端口被扫 | `ports: 5432:5432` 暴露 | 不发布端口 |
| Windows 挂载 SQL 目录报权限错 | 文件共享未授权该盘 | Docker Desktop → Resources → File sharing |
| `psql: FATAL: role "root" does not exist` | 没带 `-U app` | 显式指定用户 |
| 中文写入报编码错 | 客户端编码 | `PGCLIENTENCODING=UTF8` |
| Redis 重启后 count 归零 | 没挂 `/data` | 挂卷 + `--save` |
| `depends_on` 写了但顺序反了 | 用了列表语法 | 改用长语法 + `condition` |
| 应用连 `localhost` | 容器内 localhost 是自己 | 用服务名 |

## 7. 生产化改造清单

| 项 | 开发（本章） | 生产 |
| --- | --- | --- |
| 应用代码 | 绑定挂载 `./api` | 打进镜像 |
| 密码 | `.env` | `secrets` / KMS / 外部注入 |
| 数据库端口 | 不发布 | 不发布 + 独立网络 |
| 重启策略 | 默认 `no` | `unless-stopped` 或编排平台托管 |
| 资源限制 | 无 | `deploy.resources.limits`（第 29 章） |
| 日志 | `docker logs` | `logging` 驱动 + 集中收集（第 31 章） |
| 健康检查 | `pg_isready` | 应用级 `/healthz`（第 28 章） |
| 迁移 | initdb | 独立 migration 任务 |

## 8. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | postgres 镜像 initdb 说明、Redis persistence 文档、Compose `depends_on` 语义 |
| `[r3]` | 实测 | 25/25；initdb 单次执行、`:?` 报错文案、服务名解析 IP、卷生命周期均为本机实录 |

## 9. 毕业自查

- [ ] 25/25 通过
- [ ] 能画出三服务的网络与卷拓扑
- [ ] 能解释 initdb 只跑一次的判定条件与后果
- [ ] 能说出 `:?` 相比空值的优势
- [ ] 能独立把 PostgreSQL 换成 MySQL 并让验收通过
- [ ] 知道生产环境不该发布数据库端口的原因

## 10. 下一章

第 28 章专攻"启动顺序"：`healthcheck` 的写法、`depends_on` 三种 condition、`restart` 策略、以及为什么健康检查不能替代应用层重试。
