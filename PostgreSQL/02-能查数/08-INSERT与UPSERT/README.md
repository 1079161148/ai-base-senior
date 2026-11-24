# 08 INSERT 与 UPSERT

## 一句话结论

`INSERT` 有四种进阶写法：一次多行、省略列（用 `DEFAULT`/`NULL`）、`INSERT ... SELECT` 从别的表搬数据、`RETURNING` 直接拿回刚插入的行。PostgreSQL 独有 `ON CONFLICT ... DO UPDATE/NOTHING`，也就是 UPSERT，用 `EXCLUDED` 引用原本要插入的新值。

## 最小可运行案例

```sql
INSERT INTO students (name, email) VALUES ('张三','z@x.com')
ON CONFLICT (email) DO UPDATE SET age = EXCLUDED.age
RETURNING id;
```

## 怎么跑

```powershell
cd "02-能查数\08-INSERT与UPSERT\examples"
uv run python verify.py
```

## 核心 API 速查

| 语法 | 作用 |
| --- | --- |
| `VALUES (...), (...)` | 一次插多行 |
| `INSERT ... SELECT` | 查询并插入 |
| `RETURNING *` | 返回插入的行 |
| `ON CONFLICT (col) DO UPDATE` | 冲突时更新 |
| `EXCLUDED.col` | 本来要插入的新值 |
| `DO NOTHING` | 冲突时跳过 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 省略列名 VALUES | 列顺序一变就错位 | 显式列清单 |
| UPSERT 无唯一约束 | 报错无冲突目标 | 给冲突列加 UNIQUE |
| 用 `VALUES(...)` 当新值 | 语义错误 | 用 `EXCLUDED` |
| 以为 RETURNING 只支持 INSERT | 实际 DELETE/UPDATE 也支持 | 三处都能用 |

## 毕业自查

- [ ] 8/8 通过
- [ ] 能解释 `EXCLUDED` 是什么
- [ ] 动手题：删掉 `name_unique` 约束看 UPSERT 报什么
