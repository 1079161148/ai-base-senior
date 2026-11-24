# 11 聚合、分组与 HAVING

## 一句话结论

`COUNT/SUM/AVG/MAX/MIN` 把多行压成一行；`GROUP BY` 让聚合按组进行；`HAVING` 在分组**之后**过滤，而 `WHERE` 在分组**之前**过滤。执行顺序：`FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT`。

## 最小可运行案例

```sql
SELECT age, AVG(score) AS 平均分
FROM students
GROUP BY age
HAVING AVG(score) >= 90
ORDER BY 平均分 DESC;
```

## 怎么跑

```powershell
cd "02-能查数\11-聚合分组与HAVING\examples"
uv run python verify.py
```

## 核心 API 速查

| 函数/子句 | 作用 |
| --- | --- |
| `COUNT(*)` | 行数，含 NULL 行 |
| `COUNT(col)` | 非 NULL 值个数 |
| `SUM/AVG/MAX/MIN` | 聚合，忽略 NULL |
| `GROUP BY` | 分组 |
| `HAVING` | 分组后过滤 |
| `COUNT(DISTINCT col)` | 去重计数 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 在 WHERE 里用聚合函数 | 报错 | 用 HAVING |
| SELECT 非聚合列未进 GROUP BY | 报错 | 加入 GROUP BY |
| 用 `COUNT(col)` 数行 | NULL 被漏 | `COUNT(*)` |
| 以为 AVG 计入 NULL | 不计入 | 用 COALESCE 处理 |

## 毕业自查

- [ ] 12/12 通过
- [ ] 能背出 SQL 子句执行顺序
- [ ] 动手题：把 HAVING 条件移到 WHERE，看报什么错
