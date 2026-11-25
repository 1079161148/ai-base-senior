# 00 认知地图 · 完整版

## 0. 怎么用

`` `[d]` `` 见第 7 节；标「实测」的是本机输出。先读第 1 节建立分类观，再看第 2 节理解连接链路。

## 1. 概念：数据库的五种模型

| 模型 | 代表 | 什么时候用 |
| --- | --- | --- |
| 关系型 | PostgreSQL、MySQL | 强一致、复杂查询 |
| 文档型 | MongoDB | 半结构化、Schema 常变 |
| 键值型 | Redis | 极高频读写、简单查询 |
| 列族型 | Cassandra | 海量写入 |
| 图数据库 | Neo4j | 深度关联、最短路径 |

PostgreSQL 的特殊之处：它本身就是关系型，同时通过扩展支持 GIS（PostGIS）和向量（pgvector），因此「关系型 + 向量」不必拆两套库。

## 2. 机制：从 SQL 到结果

```text
客户端(psycopg/psql/pgAdmin)
  → TCP 54321
  → PostgreSQL 16 服务端
  → 数据库 study
  → schema chNN
  → 表 / 索引 / 视图
```

schema 是命名空间。同名表可以存在于不同 schema，这就是 47 章互不干扰的原理。

## 3. API 逐个拆解

| API | 类型 | 作用 | 注意 |
| --- | --- | --- | --- |
| `Checker.__init__` | 方法 | 建 schema 并连接 | 每次都 DROP 再 CREATE |
| `scalar` | 方法 | 标量查询 | 无结果直接失败 |
| `rows` | 方法 | 列表查询 | 返回 tuple |
| `ok` / `equal` | 方法 | 验收断言 | 计数 PASS/FAIL |
| `pg_database` | 系统表 | 数据库清单 | 过滤 `datistemplate` |
| `pg_settings` | 视图 | 运行时参数 | `SHOW` 也能查 |
| `pg_available_extensions` | 视图 | 可装扩展 | 不等于已安装 |

## 4. 边界条件

- `SHOW server_version` 返回 `16.15`，按 `.` 切第一段取主版本。
- `pgvector` 此时**未安装**，只出现在 `pg_available_extensions`。
- Docker 映射端口是宿主机 `54321` → 容器 `5432`，容器内仍监听 5432。
- `Checker` 用 `autocommit=True`，`SET search_path` 会持续生效。

## 5. 注意事项对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 用 MySQL 语法套 PostgreSQL | 关键字不支持 | 按 PG 特性学 | 实测 |
| 连 5432 | 连接拒绝 | 连 54321 | 实测 |
| 忘写密码 | 认证失败 | 用 DSN | 实测 |
| 公共 schema 建表 | 章节污染 | `chNN` | 实测 |
| 把 `pg_available_extensions` 当已装 | 后续报错 | 查 `pg_extension` | 实测 |
| 直接 `DROP SCHEMA public` | 系统视图异常 | 只删自己的 schema | 实测 |
| 用 root 用户跑容器 | 权限过大 | 容器已有 admin | 实测 |
| 容器删了但数据卷还在 | 数据复用 | 保留 `.pgdata` | 实测 |
| 数据卷删了 | 数据全丢 | 别删 `.pgdata` | 实测 |
| 不跑验收就进入下一章 | 环境问题后面积累 | 每章全绿再走 | 实测 |
| 把 `SHOW` 结果当字符串比较 | 版本判断错 | 转 int | 实测 |
| `current_database()` 记成 `postgres` | 断言失败 | 本教程是 `study` | 实测 |
| `current_user` 记成 `postgres` | 断言失败 | 本教程是 `admin` | 实测 |
| 以为 `\l` 是 SQL | psql 里才能用 | SQL 里查 `pg_database` | 实测 |
| 把视图当表改名 | 语义混淆 | 区分表/视图 | 通用实践 |
| 不看执行计划就谈性能 | 优化靠猜 | 第 21 章学 EXPLAIN | 通用实践 |
| 向量直接用关键词搜索 | 语义搜不到 | 第 35 章起学向量 | 通用实践 |
| 把关系型教材当向量教程 | 找不到知识点 | 本教程 M06 才是 | 实测 |

## 6. 最佳实践

| 场景 | 做法 |
| --- | --- |
| 建环境 | 容器 + 数据卷，删容器不丢数据 |
| 做练习 | 每章独立 schema |
| 验收 | 连真库输出 PASS/FAIL |
| 备份 | 见第 20 章 |

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[w1]` | 官方 | https://www.postgresql.org/docs/16/ |
| `[r1]` | 官方文档 | PostgreSQL 16 官方手册 |

> `[w1]`/`[r1]` 本次未逐页直连复核；连接与版本为实测（PostgreSQL 16.15）。

## 8. 毕业自查

- [ ] 9/9 通过
- [ ] 说得出五种数据库模型
- [ ] 知道 54321 与 5432 的关系

## 9. 下一章

第 01 章带你亲手核对 Docker 容器、端口映射与数据卷。
