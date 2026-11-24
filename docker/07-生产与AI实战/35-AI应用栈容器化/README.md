# 35 AI 应用栈容器化

## 一句话结论

一套 AI 应用的容器拓扑就四块：**db（pgvector）+ cache（redis）+ tools（工具网关）+ agent（编排层）**。关键设计是"**提示词、模型、工具都不进镜像**"，镜像只放能跑起来的代码。

## 最小可运行案例

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD:?}
      POSTGRES_DB: ai
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d ai"]
  agent:
    image: python:3.12-slim
    volumes:
      - ./agent:/app:ro
      - ./prompts:/prompts:ro     # 提示词外置
    environment:
      DB_HOST: db
      TOOLS_URL: http://tools:8001
    depends_on:
      db: { condition: service_healthy }
```

## 怎么跑

```powershell
cd "07-生产与AI实战\35-AI应用栈容器化\examples"
uv run python verify.py
```

## 本机实测（22/22）

| 断言 | 实测 |
| --- | --- |
| 服务清单 | `agent` / `cache` / `db` / `tools` |
| pgvector 扩展 | `pg_extension` 有 `vector` |
| 向量列类型 | `vector`（`vector(3)`） |
| 索引 | `docs_embedding_idx` 使用 `hnsw` |
| 余弦检索 `embedding <-> '[1,0,0]'` | 返回 `docker 容器编排` |
| 初始化数据 | 4 行 |
| Redis | `SETEX`/`GET` 正常，`appendonly=yes` |
| agent `/healthz` | `db=up`、`redis=up` |
| agent→tools | 通过服务名 `tools:8001` 取到 3 个工具 |
| `/chat` | 返回 answer + tools + prompt_chars |
| 网络 | 4 容器都在 `ch35-net` |
| db 端口 | `PortBindings = {}`（未暴露） |
| devcontainer.json | 指向 compose 的 `agent` 服务 |
| `down` → `up` | 4 行向量数据仍在 |
| `down -v` | 卷被删除 |

## 拓扑

```text
                 ┌──────────────── ch35-net ────────────────┐
  127.0.0.1:18095│                                          │
        │        │  agent ──HTTP──► tools:8001（工具网关）    │
        ▼        │    │                                     │
     agent:8000  │    ├──TCP:5432──► db（pgvector）          │
                 │    └──TCP:6379──► cache（redis + AOF）    │
                 │         ▲ 提示词 /prompts:ro             │
                 └──────────────────────────────────────────┘
```

| 容器的职责 | 为什么单独拆 |
| --- | --- |
| `db` | 向量与业务数据要持久化、可备份、可扩展 |
| `cache` | 会话/答案缓存，重启不丢（AOF） |
| `tools` | 工具是独立生命周期：可单独升级、限权、审计 |
| `agent` | 编排逻辑，迭代最快，挂源码热改 |

## 四个工程原则

### 1. 提示词外置

```yaml
volumes:
  - ./prompts:/prompts:ro
```

改提示词不需要重建镜像、不需要重启容器（下次请求读到新文件）。生产可用 ConfigMap / 配置中心，但在容器层就是**只读挂载**。

### 2. 工具拆成独立服务

| 做法 | 问题 |
| --- | --- |
| 工具函数写在 agent 进程里 | 无法独立扩缩、升级要重启 agent、越权难控制 |
| 工具做独立容器（HTTP/SSE/stdio） | 可独立限权、独立版本、独立审计 |

这与 **MCP（Model Context Protocol）** 的模型一致：工具是 server，Agent 是 client。MCP 三种传输对应到容器：

| 传输 | 容器形态 | 适用 |
| --- | --- | --- |
| stdio | 同 Pod/同 compose 项目的子进程（`docker exec`/sidecar） | 本地工具 |
| HTTP/SSE | 独立服务 + 端口暴露 | 多 Agent 共享 |
| WebSocket | 独立服务 | 长连接推送 |

### 3. 模型与数据外置

| 内容 | 位置 |
| --- | --- |
| 权重 | 宿主目录/对象存储，只读挂载（第 34 章） |
| 向量 | pgvector 表 + 命名卷 |
| 会话 | Redis + AOF |
| 提示词 | 只读挂载 / 配置中心 |

### 4. 内部服务不发布端口

实测 `db` 的 `HostConfig.PortBindings` 是 `{}`：只在 compose 网络内可达。只有 agent 暴露 `127.0.0.1:18095`。

## pgvector 速查

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE docs (
  id serial PRIMARY KEY,
  content text NOT NULL,
  embedding vector(3) NOT NULL
);

-- 余弦距离索引（HNSW）
CREATE INDEX ON docs USING hnsw (embedding vector_cosine_ops);
```

| 运算符 | 含义 | 索引类型 |
| --- | --- | --- |
| `<->` | L2 距离 | `vector_l2_ops` |
| `<#>` | 负内积 | `vector_ip_ops` |
| `<=>` | 余弦距离 | `vector_cosine_ops` |

```sql
-- 最近邻
SELECT content FROM docs ORDER BY embedding <=> '[1,0,0]' LIMIT 5;

-- 带阈值过滤
SELECT content FROM docs WHERE embedding <=> '[1,0,0]' < 0.3 ORDER BY 1 LIMIT 5;
```

HNSW vs IVFFlat：

| 维度 | HNSW | IVFFlat |
| --- | --- | --- |
| 查询速度 | 快 | 中 |
| 构建速度 | 慢 | 快 |
| 内存占用 | 高 | 低 |
| 是否需要训练数据 | 否 | **需要**（先有数据再建） |
| 适用 | 大多数在线检索 | 数据量大、内存紧张 |

## DevContainer

`.devcontainer/devcontainer.json` 本章实测可解析，关键字段：

```json
{
  "dockerComposeFile": "../compose.yaml",
  "service": "agent",
  "workspaceFolder": "/app",
  "shutdownAction": "stopCompose",
  "forwardPorts": [8000, 5432, 6379]
}
```

| 字段 | 作用 |
| --- | --- |
| `dockerComposeFile` | 复用生产编排，环境一致 |
| `service` | 进入哪个容器开发 |
| `shutdownAction` | 关闭窗口时是否停掉整套 |
| `forwardPorts` | 自动转发端口 |

**收益**：新人 `clone → Reopen in Container` 就有完整环境，不需要装 Python/pgvector/redis 客户端。

## 常用命令

```bash
docker compose up -d
docker compose exec -T db psql -U app -d ai -c "\dx"            # 看扩展
docker compose exec -T db psql -U app -d ai -c "select count(*) from docs"
docker compose exec -T cache redis-cli keys 'answer:*'
docker compose exec -T agent python -c "import urllib.request;print(urllib.request.urlopen('http://tools:8001/tools').read())"
docker compose logs -f agent tools
docker compose down            # 保留向量
docker compose down -v         # 重置（initdb 会重跑）
```

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `type "vector" does not exist` | 没执行 `CREATE EXTENSION` | initdb 里加，或用 `pgvector` 镜像 |
| 初始化 SQL 改了没生效 | 数据卷已存在 | `down -v` 重建 |
| 检索没走索引 | 数据太少 / 算子与索引不匹配 | 确认 `<=>` 对 `vector_cosine_ops` |
| IVFFlat 索引空表创建失败 | 需要训练数据 | 先插入足够数据再建索引 |
| 向量维度不一致 | 模型换版本 | 维度写进表结构并校验 |
| agent 启动即失败 | 依赖没就绪 | `condition: service_healthy` |
| 提示词改了不生效 | 打进了镜像 | 改挂载 |
| Redis 重启丢会话 | 没开 AOF | `--appendonly yes` |
| 工具越权 | 工具与 agent 同进程 | 拆独立服务 + 最小权限 |
| 容器内存被吃满 | 向量化批量太大 | 分批 + `--memory` 限流 |
| devcontainer 起不来 | `dockerComposeFile` 路径错 | 相对 `.devcontainer/` 解析 |

## 毕业自查

- [ ] 22/22 通过
- [ ] 能画出四容器拓扑并解释每个容器的职责
- [ ] 能写出 pgvector 的建表/索引/检索三条 SQL
- [ ] 能说出 HNSW 与 IVFFlat 的取舍
- [ ] 能解释为什么工具要拆成独立服务（对照 MCP 模型）
- [ ] 能说出提示词、模型、数据分别该放哪
- [ ] 能写一份 devcontainer.json 复用 compose
