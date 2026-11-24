# 03 SQL 分类

## 一句话结论

SQL 分四类：**DDL 定义结构**（`CREATE`/`ALTER`/`DROP`/`TRUNCATE`）、**DML 操作数据**（`INSERT`/`SELECT`/`UPDATE`/`DELETE`）、**DCL 管权限**（`GRANT`/`REVOKE`）、**TCL 控事务**（`BEGIN`/`COMMIT`/`ROLLBACK`）。这一章用 9 条断言把四类各跑一遍，并用序列证明 `TRUNCATE` 属于 DDL。

## 最小可运行案例

```sql
CREATE TABLE t03 (id int PRIMARY KEY, val text);      -- DDL
INSERT INTO t03 VALUES (1, 'a');                       -- DML
BEGIN;                                                 -- TCL
UPDATE t03 SET val = 'A' WHERE id = 1;
ROLLBACK;
SELECT * FROM t03;                                     -- 仍是 'a'
```

## 怎么跑

```powershell
cd "01-能建表\03-SQL分类\examples"
uv run python verify.py    # 结果：8/8 通过
```

## 核心 API 速查

| 分类 | 关键字 | 作用 |
| --- | --- | --- |
| DDL | `CREATE`/`ALTER`/`DROP`/`TRUNCATE` | 改结构 |
| DML | `INSERT`/`SELECT`/`UPDATE`/`DELETE` | 改数据 |
| DCL | `GRANT`/`REVOKE` | 改权限 |
| TCL | `BEGIN`/`COMMIT`/`ROLLBACK`/`SAVEPOINT` | 改事务边界 |
| 函数 | `has_table_privilege()` | 查权限 |
| 序列 | `nextval('t_id_seq')` | 自增计数器 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 把 `TRUNCATE` 当 DML | 分类错、以为能带 WHERE | 它是 DDL |
| 认为 `SELECT` 不算 DML | 漏记一类 | SQL 标准把查询归入 DML |
| `DELETE` 后以为 id 从 1 开始 | 序列没重置 | `TRUNCATE ... RESTART IDENTITY` |
| 在 autocommit 连接里 `ROLLBACK` | 不生效 | 另开普通连接 |

## 毕业自查

- [ ] 8/8 通过
- [ ] 能说出四类各两个关键字
- [ ] 动手题：把 `TRUNCATE` 改成 `DELETE`，看哪条断言变红
