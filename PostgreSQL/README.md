# PostgreSQL 从 0 到 1 · 47 章实战教程

## 一句话结论

47 章覆盖关系型数据库的全部核心技能（建表、查询、事务、索引、生产进阶），并补齐 **pgvector 向量数据库** 的完整链路（安装、类型、距离算子、索引、混合检索、RAG、评测），最后 1 章做工程化毕业项目。每章都有连真库执行的 `verify.py`，47 章共用一个 pg16 容器。

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

## 教程定位

覆盖关系型数据库的完整技能链，并补足向量检索：

- 前 35 章从建表、查询、事务一路到索引、视图、JSONB、权限、复制与建模评审
- 后 11 章专讲 pgvector：安装、`vector` 类型、距离算子、IVFFlat/HNSW、混合检索、RAG、评测
- 最后 1 章做工程化毕业项目（电商库 + 语义搜索）

设计取舍：

- 统一使用本教程自建的 pg16 容器（端口 54321、库 `study`），消除环境差异
- 每章一个独立 schema（`ch00` … `ch46`），验收可重复执行、互不污染
- 一致性以 PostgreSQL 16 的实际行为为准，凡与常见资料冲突处以实测结果为准

## 依据与未验证项

- SQL 语法与行为以 PostgreSQL 16 官方手册为准，冲突处以实测为准
- pgvector 相关章节以官方文档为准，参数名在落地时复核
- 真实 `docker build`、K8s、生产复制集群不在本教程实测范围
