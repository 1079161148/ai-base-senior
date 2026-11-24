# 22 B-tree 与联合索引

## 一句话结论

B-tree 擅长等值和范围查询；联合索引遵守**最左前缀**原则；只查索引列时走 `Index Only Scan`；部分索引只索引满足条件的行；表达式索引给 `lower(name)` 这类计算列加速。

## 最小可运行案例

```sql
CREATE INDEX idx_dept_age ON orders(dept_id, created_at);
EXPLAIN SELECT * FROM orders WHERE dept_id=3 AND created_at > '2024-01-01';
```

## 怎么跑

```powershell
cd "04-能跑快\22-Btree与联合索引\examples"
uv run python verify.py
```

## 核心 API 速查

| 索引类型 | 适用场景 |
| --- | --- |
| B-tree | 等值、范围、排序 |
| 联合索引 | 多条件，最左前缀 |
| UNIQUE | 唯一约束 |
| 部分索引 | 只覆盖子集 |
| 表达式索引 | 计算列查询 |
| Index Only Scan | 只查索引列 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 联合索引跳过最左列 | 用不上 | 调整列顺序 |
| 每列都建单列索引 | 写放大 | 按查询建联合 |
| 小表建索引 | 优化器仍走 Seq Scan | 足够数据量 |
| 索引列上套函数 | 失效 | 建表达式索引 |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能解释最左前缀
- [ ] 动手题：把联合索引改成 `(age, dept)` 看计划变化
