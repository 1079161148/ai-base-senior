# 19 UPDATE 与 DELETE 高级用法

## 一句话结论

`UPDATE`/`DELETE` 最容易出的事故是忘写 `WHERE`。PostgreSQL 的 `RETURNING` 能在一条语句里拿回被改/被删的行，`UPDATE ... FROM` 能用另一张表的数据更新，避免写循环。

## 最小可运行案例

```sql
UPDATE students s SET score=e.score
FROM exam_scores e WHERE s.id=e.student_id
RETURNING s.id, s.score;
```

## 怎么跑

```powershell
cd "03-能保证正确\19-UPDATE与DELETE高级用法\examples"
uv run python verify.py
```

## 核心 API 速查

| 语法 | 作用 |
| --- | --- |
| `SET a=..., b=...` | 多列更新 |
| `SET col=col+1` | 表达式更新 |
| `UPDATE ... FROM` | 跨表更新 |
| `RETURNING` | 返回受影响行 |
| `DELETE ... RETURNING` | 返回被删行 |
| `TRUNCATE RESTART IDENTITY` | 重置序列 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| UPDATE/DELETE 忘 WHERE | 全表被改 | 先 SELECT 验证 |
| 以为 DELETE 重置序列 | id 继续涨 | TRUNCATE RESTART IDENTITY |
| UPDATE FROM 无 WHERE | 笛卡尔更新 | 加关联条件 |
| RETURNING 当 SELECT 用 | 语义不同 | 它只返回受影响行 |

## 毕业自查

- [ ] 12/12 通过
- [ ] 能写跨表更新
- [ ] 动手题：故意去掉 WHERE，观察多少行被改（在自己的 schema 里）
