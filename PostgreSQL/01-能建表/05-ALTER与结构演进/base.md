# 05 ALTER 与结构演进 · 完整版

## 0. 怎么用

先跑 12/12，再读第 4 节理解哪些变更会锁表。

## 1. 概念

表结构不是一次定死的。DDL 让结构可演进，但每条 DDL 都可能持有强锁。

## 2. 机制

```text
ALTER TABLE → 取 ACCESS EXCLUSIVE 锁 → 改 pg_catalog → 提交
                    ↑
              阻塞该表所有读写
```

## 3. API 逐个拆解

| API | 作用 | 注意 |
| --- | --- | --- |
| `information_schema.columns` | 查列元数据 | 验证 ALTER 结果 |
| `pg_constraint` | 查约束 | `conname` 是约束名 |
| `to_regclass` | 判断对象存在 | 不存在返回 NULL |
| `USING` | 类型转换规则 | 如 `score::INTEGER` |
| `RESTART IDENTITY` | 重置序列 | 只作用于 TRUNCATE |

## 4. 边界条件

- `SET DEFAULT` 只影响之后的插入，不改已有行。
- `SET NOT NULL` 要求表中没有 NULL。
- `TRUNCATE` 在 PostgreSQL 中可回滚，MySQL 不行。
- `DROP COLUMN` 若有视图依赖会失败。

## 5. 注意事项对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 改类型不加 USING | cast 错误 | 显式转换 | 原仓库 02 |
| DROP DEFAULT 当删列 | 列还在 | DROP COLUMN | 实测 |
| TRUNCATE 不重置序列 | id 继续涨 | RESTART IDENTITY | 实测 |
| DROP TABLE 被外键阻塞 | 依赖错误 | CASCADE 或先删子表 | 原仓库 03 |
| ADD NOT NULL 前有 NULL | 失败 | 先 UPDATE | 实测 |
| ADD CHECK 前有坏数据 | 失败 | 先清理 | 实测 |
| RENAME 后旧名引用失效 | 视图报错 | 同步改依赖 | 实测 |
| DROP IF EXISTS 幂等 | 重复执行不报错 | 推荐 | 原仓库 02 |
| 不加 CONSTRAINT 名字 | 系统自动生成 | 显式命名 | 实测 |
| 生产高峰跑 DDL | 长时间锁表 | 低峰期 | 实测 |
| 以为 TRUNCATE 能带 WHERE | 语法错误 | 用 DELETE | 原仓库 02 |
| DELETE 不重置序列 | id 有空洞 | TRUNCATE | 实测 |
| 不查 information_schema | 靠猜 | 查元数据 | 实测 |
| CASCADE 滥用 | 误删视图 | 先查依赖 | 原仓库 03 |
| 改列类型丢精度 | NUMERIC→INT | 先评估 | 实测 |
| 不备份就 DROP | 数据不可恢复 | 第 20 章 | 原仓库 07 |
| 事务里 TRUNCATE 后回滚 | 数据恢复 | PG 支持 | 实测 |
| 用 `ALTER TABLE ONLY` | 不处理子表 | 需要时显式写 | 实测 |

## 6. 最佳实践

演进脚本版本化（第 46 章），每次 DDL 前先看依赖与锁。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | 原仓库 | 02 DDL 课件 |

> 本次实测 12/12，`88.5::INTEGER` 得到 89（四舍五入）。

## 8. 毕业自查

- [ ] 12/12 通过
- [ ] 能说出三种会锁表的 DDL

## 9. 下一章

第 06 章学表间关系：1:1、1:N、M:N 与外键行为。
