# PostgreSQL 从 0 到 1 · 47 章实战教程

## 一句话结论

基于 Gitee `dev-edu/database` 的 7 章 PostgreSQL 课程骨架扩展而成：前 35 章覆盖关系型数据库的全部核心技能（建表、查询、事务、索引、生产进阶），后 11 章补齐原仓库只提了一行的 **pgvector 向量数据库**，最后 1 章做工程化毕业项目。每章都有连真库执行的 `verify.py`，47 章共用一个 pg16 容器。

## 环境（一次性）

```powershell
cd E:\ai-agent-study\PostgreSQL
uv sync

# 容器已由本教程创建：pg16-study，端口 54321，库 study，用户 admin / study123
docker ps --filter name=pg16-study
```

如容器不存在，重建命令：

```powershell
docker run -d --name pg16-study `
  -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=study123 -e POSTGRES_DB=study `
  -p 54321:5432 `
  -v "E:/ai-agent-study/PostgreSQL/.pgdata:/var/lib/postgresql/data" `
  postgres:16-alpine
```

## 怎么学（每章固定五步）

| 步骤 | 做什么 |
| --- | --- |
| 1 跑通 | 照抄本章 SQL，先看到结果 |
| 2 看懂 | 用 `EXPLAIN` 或 ERD 看框架做了什么 |
| 3 改坏 | 故意去掉 `WHERE`、删索引、改隔离级别 |
| 4 修好 | 自己写回来 |
| 5 自测 | `uv run python verify.py`，必须全绿 |

**每章一个独立 schema**（`ch00` … `ch46`），跑验收会 `DROP SCHEMA CASCADE`，不会污染其他章。

## 章节目录

| 模块 | 章节 | 主题 |
| --- | --- | --- |
| M00 能连上 | 00–02 | 认知地图、Docker 环境、psql 与 pgAdmin |
| M01 能建表 | 03–07 | SQL 分类、CREATE、ALTER、表间关系、三范式 |
| M02 能查数 | 08–15 | INSERT、SELECT、聚合、JOIN、CTE、窗口函数、33 题实战 |
| M03 能保证正确 | 16–20 | 事务、并发异常、隔离级别与锁、备份恢复 |
| M04 能跑快 | 21–26 | EXPLAIN、B-tree、索引失效、GIN/GiST/BRIN、VACUUM、分区 |
| M05 能进生产 | 27–34 | 视图、存储过程、JSONB、权限、FDW、复制、锁、建模评审 |
| M06 向量数据库 | 35–45 | pgvector 安装、vector 类型、距离算子、IVFFlat/HNSW、混合检索、RAG、评测 |
| M07 毕业项目 | 46 | 电商库 + 语义搜索工程化 |

## 与原仓库的关系

原仓库 `dev-edu/database` 只有 7 章课件，`pgvector` 仅在 `07 拓展知识 → 插件机制` 表格中作为举例出现一行。本教程：

- 保留原仓库 7 章的知识骨架与电商库案例
- 修正原课件三处不一致（密码 `123123`/`admin123`、库名 `admin`/`demo_db`、幻读示例缺 `id`）
- 把 7 章拆成 35 个可验收的小步骤
- 新增 M06 的 11 章完整向量数据库内容
- 所有验收脚本连真库执行，不是静态文本检查

## 依据与未验证项

- 原仓库内容已通过 Gitee API v5 与 raw 文件逐章核对（2026-11-21）
- pgvector 相关章节以官方文档为准，参数名会在落地时复核
- 真实 `docker build`、K8s、生产复制集群不在本教程实测范围
