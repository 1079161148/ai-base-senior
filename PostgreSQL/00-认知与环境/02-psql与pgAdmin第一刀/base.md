# 02 psql 与 pgAdmin 第一刀 · 完整版

## 0. 怎么用

先跑 10/10 验收建立手感，再读第 2 节理解客户端与服务端的边界。

## 1. 概念

psql 和 pgAdmin 都是客户端。它们发的才是 SQL；`\l` 这类反斜杠命令由客户端自己处理，服务端根本看不到。

## 2. 机制

```text
psql \l        → 客户端查 pg_database  → 输出表格
psql SELECT    → 原样发给服务端        → 返回结果
psql \q        → 客户端断开连接        → 没有 SQL
```

## 3. API 逐个拆解

| API | 类型 | 作用 | 注意 |
| --- | --- | --- | --- |
| `pg_database` | 系统表 | 数据库清单 | 过滤模板库 |
| `current_user` | 函数 | 当前用户 | 不带括号 |
| `to_regclass` | 函数 | 表名 → OID | 不存在返回 NULL |
| `information_schema.columns` | 视图 | 列信息 | 跨库标准 |
| `SERIAL` | 伪类型 | 自增 | 展开为 sequence |
| `TIMESTAMPTZ` | 类型 | 带时区时间 | 存 UTC，按时区显示 |

## 4. 边界条件

- `Checker` 使用 autocommit，所以演示回滚必须另开普通连接。
- `information_schema` 只显示当前用户有权限的对象。
- `DROP TABLE` 默认不允许删除被外键引用的表，需 `CASCADE`。

## 5. 注意事项对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| SQL 里写 `\l` | 语法错误 | 查 `pg_database` | 实测 |
| SQL 里写 `\q` | 语法错误 | 断开连接 | 实测 |
| autocommit 连接回滚 | 无效 | 另开连接 | 实测 |
| 不显式列名 INSERT | 顺序敏感 | 写列清单 | 实测 |
| 用 `password` 当列名 | 保留字冲突 | 换名或加引号 | 通用实践 |
| 用 `TIME` 存日期 | 数据丢失 | `TIMESTAMP` | 通用实践 |
| 用 `REAL` 存金额 | 精度误差 | `NUMERIC` | 通用实践 |
| 不设 `NOT NULL` | 脏数据 | 显式约束 | 通用实践 |
| 建表不设主键 | 无法唯一定位 | `PRIMARY KEY` | 通用实践 |
| `DROP TABLE` 不加 `IF EXISTS` | 重复执行报错 | 加 `IF EXISTS` | 通用实践 |
| 把 `TRUNCATE` 当 DML | 分类错误 | 它是 DDL | 通用实践 |
| 用 `VARCHAR(50)` 存超长文本 | 截断报错 | 用 `TEXT` | 通用实践 |
| 不关连接 | 占连接数 | `with` 或 `close()` | 实测 |
| 在 public schema 建测试表 | 污染 | 用 `ch02` | 实测 |
| 把 `current_database()` 写错 | 断言失败 | 不加括号 | 实测 |
| 以为 `\l` 能带 WHERE | 客户端不支持 | 用 SQL | 实测 |
| 不看 `EXPLAIN` 就说慢 | 无证据 | 第 21 章 | 通用实践 |
| 跳过 psql 只用 pgAdmin | 不会命令行排障 | 两个都会 | 通用实践 |

## 6. 最佳实践

日常查询用 pgAdmin 看 ERD，排障和自动化用 psql/psycopg。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | 官方文档 | PostgreSQL 16 官方手册 |

> 本次实测：10/10，事务回滚后行数保持 2。

## 8. 毕业自查

- [ ] 10/10 通过
- [ ] 能区分元命令与 SQL

## 9. 下一章

M01 开始系统学 DDL：先分清 SQL 四大类，再建表。
