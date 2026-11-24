# 12 JOIN 四种连接

## 一句话结论

`INNER` 只保留匹配行；`LEFT` 保留左表全部、右表补 NULL；`RIGHT` 反之；`FULL` 两边都保留。多表连接靠别名区分，`LEFT JOIN ... WHERE 右表列 IS NULL` 是找「没有关联记录」的标准写法。

## 最小可运行案例

```sql
SELECT u.username, o.order_no
FROM users u LEFT JOIN orders o ON u.id = o.user_id
ORDER BY u.id;
```

## 怎么跑

```powershell
cd "02-能查数\12-JOIN四种连接\examples"
uv run python verify.py
```

## 核心 API 速查

| 语法 | 保留哪些行 |
| --- | --- |
| `INNER JOIN` | 两边都匹配 |
| `LEFT JOIN` | 左表全部 |
| `RIGHT JOIN` | 右表全部 |
| `FULL JOIN` | 两边全部 |
| `CROSS JOIN` | 笛卡尔积 |
| `USING(col)` | 同名列简写 |
| `ON` | 连接条件 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| LEFT JOIN 后 WHERE 右表列 | 退化成 INNER | 条件写 ON |
| 忘写 ON 条件 | 笛卡尔积 | 显式 ON |
| 多表无别名 | 列名歧义 | 每张表起别名 |
| 把 `USING` 当 `ON` | 只能用于同名列 | 不同名用 ON |

## 毕业自查

- [ ] 13/13 通过
- [ ] 能解释 LEFT JOIN 找孤儿为什么用 IS NULL
- [ ] 动手题：把 LEFT 改成 INNER，看行数怎么变
