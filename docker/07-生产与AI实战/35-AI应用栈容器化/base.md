# 35 AI 应用栈容器化 · 完整版

## 0. 怎么用

跑 22/22。本章把前面 34 章的能力串成一个真实系统：向量库（第 12–14 章卷）、服务名寻址（第 16 章）、健康检查（第 28 章）、Compose 编排（第 26–29 章）、AI 场景（第 34 章）。

## 1. 为什么 AI 应用要这样拆

| 组件 | 变化频率 | 状态 | 隔离理由 |
| --- | --- | --- | --- |
| `agent` 编排逻辑 | 每天 | 无状态 | 迭代快，挂源码热改 |
| `tools` 工具 | 每周 | 通常无状态 | 权限边界，独立扩缩 |
| `db` 向量库 | 很少 | **有状态** | 数据是资产，要备份/迁移 |
| `cache` 会话 | 从不 | 半状态 | 重启需可恢复（AOF） |

按"变化频率 + 状态"拆容器，是微服务拆分的基本依据，AI 场景同样适用。

## 2. 拓扑与寻址

```text
宿主机 127.0.0.1:18095
        │
┌───────┴──────────── ch35-net（内置 DNS）──────────────────┐
│  agent ──http://tools:8001──► tools                      │
│    │                                                     │
│    ├──tcp db:5432──► db (pgvector)  ◄── pgdata 卷         │
│    └──tcp cache:6379──► cache (redis) ◄── redisdata 卷    │
│         /prompts (ro)  /app (ro)                          │
└──────────────────────────────────────────────────────────┘
```

实测：`agent` 容器内 `urllib.request.urlopen('http://tools:8001/tools')` 直接可用，不写任何 IP。

## 3. pgvector：把向量检索放回数据库

### 3.1 为什么不用独立向量库

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| pgvector | 事务一致性、SQL 过滤、备份复用现有运维 | 超大规模（亿级）性能不如专用库 |
| Milvus/Qdrant | 专为向量优化、水平扩展 | 多一套系统要运维 |
| 内存索引（faiss） | 极快 | 无持久化、无并发控制 |

**百万级以下几乎都该用 pgvector**：能用一条 SQL 把"向量相似 + 业务过滤"一起做完。

### 3.2 建表与索引

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE docs (
    id        serial PRIMARY KEY,
    content   text NOT NULL,
    embedding vector(3) NOT NULL
);

CREATE INDEX docs_embedding_idx ON docs USING hnsw (embedding vector_cosine_ops);
```

本章实测：

| 检查 | 结果 |
| --- | --- |
| `pg_extension` 含 vector | 是 |
| `pg_attribute` 类型 | `vector`（3 维） |
| `pg_indexes.indexdef` | 含 `hnsw` |

### 3.3 三种距离与算子

| 距离 | 算子 | 索引 opclass | 用途 |
| --- | --- | --- | --- |
| L2 | `<->` | `vector_l2_ops` | 图像特征 |
| 内积 | `<#>` | `vector_ip_ops` | 归一化后等价余弦 |
| 余弦 | `<=>` | `vector_cosine_ops` | 文本嵌入（最常用） |

**索引 opclass 必须与查询算子匹配**，否则走不了索引（这是"加了索引还是慢"的头号原因）。

### 3.4 维度必须固定

`vector(3)` 是定长。换嵌入模型（如 768 → 1024 维）必须改表结构或新建表：

```sql
ALTER TABLE docs ALTER COLUMN embedding TYPE vector(1024);
```

所以工程上要**把模型版本与维度写进元数据表**，避免模型升级后检索全错。

## 4. 工具网关：MCP 的容器化形态

### 4.1 为什么不在 agent 里直接写工具函数

| 维度 | 同进程 | 独立服务 |
| --- | --- | --- |
| 权限 | 与 agent 相同（能读所有密钥） | 单独挂最小权限 |
| 升级 | 重启 agent | 独立发布 |
| 扩缩 | 跟着 agent | 工具调用量大可单独扩 |
| 审计 | 混在 agent 日志里 | 独立日志与限流 |
| 复用 | 只能被这个 agent 用 | 多 agent / 多团队共享 |

MCP（Model Context Protocol）就是把这件事标准化：工具是 **server**，模型侧是 **client**，传输可为 stdio / HTTP / SSE。

### 4.2 本章实现

`tools/gateway.py` 暴露：

```text
GET /tools    → {"tools":[{"name":"kb.search","params":[...]}, ...]}
GET /healthz  → {"status":"ok","tools":3}
```

`agent/agent.py` 每次请求都 `GET http://tools:8001/tools`，实测拿到 3 个工具名。

生产替换路径：

| 现状 | 生产 |
| --- | --- |
| 自写 HTTP 网关 | FastAPI + OpenAPI，自动生成工具 schema |
| 手工注册工具 | MCP server SDK（`mcp` 官方 Python/TS SDK） |
| 单实例 | 网关 + 限流（第 29 章 scale + 反代） |

## 5. 提示词、配置外置

```yaml
volumes:
  - ./prompts:/prompts:ro
```

实测 `/chat` 返回 `prompt_chars>0`，说明读到了挂载的 `system.md`。

| 内容 | 放法 | 修改代价 |
| --- | --- | --- |
| 提示词 | 只读挂载 | 改文件即生效 |
| 工具清单 | 工具服务自己声明 | 重启工具服务 |
| 模型名/温度 | 环境变量 | 重建容器 |
| 密钥 | secrets（第 29 章） | 轮换后重建 |

## 6. Redis 在 AI 栈里的三个角色

| 角色 | key 形态 | 持久化要求 |
| --- | --- | --- |
| 会话历史 | `session:{id}` | 中（丢一次影响体验） |
| 答案缓存 | `answer:{hash}` | 低（可重算） |
| 限流计数 | `rate:{user}` | 低 |

本章用 `--appendonly yes` 开 AOF，实测 `CONFIG GET appendonly` → `yes`，重启不丢会话。

## 7. DevContainer

`.devcontainer/devcontainer.json`：

```json
{
  "dockerComposeFile": "../compose.yaml",
  "service": "agent",
  "workspaceFolder": "/app",
  "shutdownAction": "stopCompose",
  "forwardPorts": [8000, 5432, 6379]
}
```

| 收益 | 说明 |
| --- | --- |
| 环境一致 | 与生产同一份 compose |
| 零本地依赖 | 宿主只装 Docker 与 VS Code |
| 新人上手快 | `Reopen in Container` 即开工 |
| 可复现 bug | 环境和同事一致 |

注意：`dockerComposeFile` 是相对 `.devcontainer/` 的路径；`service` 必须是 compose 里存在的服务名。

## 8. 逐条验收解读（22 条）

| 组 | 覆盖内容 |
| --- | --- |
| 1–3 | 配置校验、四服务、`up` 成功（含依赖就绪等待） |
| 4 | db `pg_isready` 健康 |
| 5–7 | pgvector 扩展、`vector` 列类型、HNSW 索引 |
| 8–9 | 余弦检索命中正确条目、初始化 4 行 |
| 10–12 | Redis 写读、AOF 已开启 |
| 13 | agent 能连通 db 与 redis |
| 14 | agent→tools 服务名调用 |
| 15–16 | `/chat` 结构化回答、提示词来自挂载 |
| 17–18 | 网络含 4 容器、db 未发布端口 |
| 19 | devcontainer 配置可用 |
| 20–22 | `down` 保卷、`up` 数据仍在、`down -v` 清卷 |

## 9. 坑与对策

| 现象 | 根因 | 对策 |
| --- | --- | --- |
| `type "vector" does not exist` | 未装扩展 | `CREATE EXTENSION vector` 或用 pgvector 镜像 |
| 检索慢 | 算子与 opclass 不匹配 | `<=>` 配 `vector_cosine_ops` |
| IVFFlat 建索引报错 | 空表无训练数据 | 先灌数据再建 |
| 维度不匹配插入失败 | 模型换版本 | 固定维度 + 元数据记录 |
| initdb 改动无效 | 数据卷已存在 | `down -v` |
| agent 启动失败 | 依赖未就绪 | `service_healthy` |
| 提示词不生效 | 打进了镜像 | 只读挂载 |
| 会话重启丢失 | 无 AOF | `--appendonly yes` |
| 工具越权访问密钥 | 与 agent 同进程 | 拆服务 + 最小权限 |
| devcontainer 报找不到 compose | 相对路径错 | 按 `.devcontainer/` 解析 |
| 向量批量插入慢 | 单条 INSERT | `COPY` / 批量 `INSERT` + 事务 |

## 10. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | pgvector README（算子/HNSW/IVFFlat）、MCP 规范、Dev Containers 文档 |
| `[r3]` | 实测 | 22/22；扩展安装、HNSW 索引、余弦检索结果、AOF、agent↔tools 调用、卷持久化均为本机实录 |

## 11. 毕业自查

- [ ] 22/22 通过
- [ ] 能解释四容器拆分依据（变化频率 + 状态）
- [ ] 能写出 pgvector 的建表、索引、检索 SQL
- [ ] 能说出三种距离算子与 opclass 的对应关系
- [ ] 能解释工具独立服务的四个收益
- [ ] 能说出提示词/模型/密钥/数据各自的放法
- [ ] 能配一份可用的 devcontainer.json

## 12. 下一章

第 36 章是毕业项目与排障手册：一个端到端项目、一套系统性故障排查方法、以及全教程命令速查。
