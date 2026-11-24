# 02 psql 与 pgAdmin 第一刀

## 一句话结论

`\l`、`\conninfo`、`\q` 是 psql 客户端元命令，**不是 SQL**；它们的 SQL 等价写法分别是查 `pg_database`、`current_user/current_database()`、断开连接。这一章用 10 条断言完成第一次建表、插入、查询、回滚、删表闭环。

## 最小可运行案例

```sql
CREATE TABLE first_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
INSERT INTO first_table (name) VALUES ('张三'), ('李四');
SELECT * FROM first_table;
DROP TABLE first_table;
```

## 怎么跑

```powershell
cd "00-认知与环境\02-psql与pgAdmin第一刀\examples"
uv run python verify.py
```

预期 `结果：10/10 通过`。

## 核心 API 速查

| 命令 | 类型 | 作用 |
| --- | --- | --- |
| `\l` | psql 元命令 | 列出数据库；SQL 等价查 `pg_database` |
| `\conninfo` | psql 元命令 | 当前连接；SQL 等价 `current_user`、`current_database()` |
| `\q` | psql 元命令 | 退出，无 SQL 等价 |
| `to_regclass('t')` | SQL 函数 | 判断表是否存在，不存在返回 NULL |
| `information_schema.columns` | 视图 | 查列元数据 |
| `SERIAL` | 伪类型 | 自增整数，底层是 sequence |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 在 SQL 里写 `\l` | 语法错误 | 用 `SELECT ... FROM pg_database` |
| `autocommit` 连接里调 `rollback()` | 无效 | 用不带 autocommit 的连接 |
| 以为 `SERIAL` 是真实类型 | 建表后看不到 | 它展开为 `integer + sequence` |
| 不写列名就 `INSERT` | 列顺序一变就错 | 显式列清单 |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能说出三个 psql 元命令的 SQL 等价
- [ ] 能解释为什么回滚演示要用独立连接
- [ ] 动手题：把 `DROP TABLE` 注释掉再跑，确认验收失败
