# 27 编排实战：Web + PostgreSQL + Redis

## 一句话结论

三个服务放进一个 `compose.yaml`，靠**服务名当主机名**互相访问，靠**命名卷**跨重启保数据，靠**初始化脚本 + `:?` 变量语法**把"配置错了"从运行时故障提前成启动失败。

## 最小可运行案例

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD 未设置}
      POSTGRES_DB: appdb
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./initdb:/docker-entrypoint-initdb.d:ro
  api:
    image: python:3.12-slim
    environment:
      DB_HOST: db          # ← 服务名就是主机名
    depends_on:
      db:
        condition: service_healthy
volumes:
  pgdata:
```

## 怎么跑

```powershell
cd "06-Compose编排\27-编排实战Web-DB-Redis\examples"
uv run python verify.py
```

## 本机实测（25/25）

| 步骤 | 实测结果 |
| --- | --- |
| `config -q` | 通过，服务为 `api` / `db` / `redis` |
| 空 `.env` 启动 | 立即失败：`required variable DB_PASSWORD is missing a value` |
| `up -d` | 三容器 Started |
| db / redis 健康检查 | 均为 `healthy` |
| `initdb/01-init.sql` | `articles` 2 行，表 3 列齐全 |
| `GET /` | `{"hits":1,"db":"up","redis":"up",...}` |
| 再请求一次 | `hits` 由 1 → 2，**真实自增 Redis** |
| api 内 `socket.gethostbyname("db")` | 等于 `db` 容器在 `ch27-net` 的 IP |
| 网络内容器数 | 3，IP 互不相同 |
| 手写 `INSERT` 后 | 3 行 |
| `compose down`（不带 `-v`） | 容器删、卷 `ch27-app_pgdata` 保留 |
| 再次 `up -d` | 仍 3 行——initdb 没有重复执行 |
| Redis `SET` + `SAVE` + `restart` | `GET chapter` → `ch27` |
| `down -v` | 卷被删除 |

## 三服务职责

| 服务 | 镜像 | 角色 | 关键配置 |
| --- | --- | --- | --- |
| `db` | `postgres:16-alpine` | 持久化数据 | 命名卷 + 初始化脚本 + `pg_isready` 健康检查 |
| `redis` | `redis:7-alpine` | 缓存/计数 | 命名卷 `/data` + `redis-cli ping` 健康检查 |
| `api` | `python:3.12-slim` | 应用 | 绑定挂载源码 + 服务名环境变量 + 端口映射 |

## 三条核心机制

### 1. 服务名即主机名

同一网络内，Compose 自动给每个容器注册 DNS 别名 = 服务名。所以在 `api` 里 `ping db` 就能通，IP 不用关心。

```bash
docker compose exec -T api python -c "import socket;print(socket.gethostbyname('db'))"
```

**注意：这只在同一条自定义网络内成立。** `default` 网络默认就有 DNS，`--network host` 则没有（第 15、16 章）。

### 2. 初始化脚本只跑一次

```yaml
volumes:
  - ./initdb:/docker-entrypoint-initdb.d:ro
```

`postgres` 镜像的 entrypoint 会检查 `PGDATA` 是否为空：

| 场景 | 行为 |
| --- | --- |
| 首次启动（空卷） | 按文件名顺序执行 `*.sql` / `*.sh` |
| 卷里已有数据 | **完全跳过** |
| 改了 SQL 想重跑 | 必须 `down -v` 删卷，或手动进库执行 |

同理，`POSTGRES_PASSWORD` 只在初始化时生效；卷已存在后改密码不生效（需要 `ALTER USER`）。

### 3. 依赖顺序要写 condition

```yaml
depends_on:
  db:
    condition: service_healthy
```

只写 `depends_on: [db]` 等于 `condition: service_started`——容器起来了，但数据库可能还没接受连接。`service_healthy` 会等健康检查变绿，这是"启动顺序"的正确姿势（第 28 章展开）。

## 常用命令（本项目）

```bash
docker compose up -d                      # 启动
docker compose ps                         # 状态
docker compose logs -f api                # 跟应用日志
docker compose exec -T db psql -U app -d appdb        # 进库
docker compose exec -T db psql -U app -d appdb -c "\dt"
docker compose exec -T redis redis-cli    # 进 Redis
docker compose top                        # 各容器进程
docker compose config --format json       # 渲染终态给脚本用
docker compose down                       # 停（保数据）
docker compose down -v                    # 停 + 删卷（重置环境）
```

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 改了 init SQL 没生效 | 数据目录非空，initdb 被跳过 | `down -v` 或手工执行 SQL |
| 改了 `POSTGRES_PASSWORD` 登不上 | 密码只在首次初始化写入 | 进库 `ALTER USER`，或重建卷 |
| `api` 启动即 `Connection refused` | 只用 `depends_on` 没等就绪 | `condition: service_healthy` |
| `localhost:5432` 连不上 | 容器里的 localhost 是自己 | 用服务名 `db` |
| 宿主机 `psql` 连不上 | 没发布端口（本示例故意不发布数据库端口） | 需要时加 `ports`，但**生产不要暴露数据库** |
| Redis 重启丢数据 | 没挂 `/data` 或没触发保存 | 挂卷 + `--save` |
| Windows 挂载 `./initdb` 权限报错 | Docker Desktop 文件共享需授权 | 在设置里共享该盘 |
| `down` 后数据"没了" | 其实用 `-v` 了 | 记住 `-v` 删卷 |
| 用了 `container_name` 后起不来第二个 | 名字冲突 | 删掉，用服务名 |
| 端口 18081 被占 | 上次没 `down` | `compose down` 或换端口 |

## 生产视角的三条建议

1. **数据库不发布端口**，只在内部网络可达；需要外部访问就走跳板或代理。
2. **应用代码打进镜像**，绑定挂载只用于本地开发（第 21、22 章）。
3. **密码走 secrets / 外部环境**，`.env` 只放非敏感值并加进 `.gitignore`。

## 毕业自查

- [ ] 25/25 通过
- [ ] 能解释服务名为什么能当主机名
- [ ] 能说出 initdb 只跑一次的判定条件
- [ ] 能区分 `service_started` 与 `service_healthy`
- [ ] 知道 `down` 与 `down -v` 对数据的影响
- [ ] 能独立把这套编排改成 MySQL + Nginx 版本
