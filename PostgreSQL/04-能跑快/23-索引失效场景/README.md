# 23 索引失效场景

## 一句话结论

索引不是建了就会用。前置 `%` 的 `LIKE`、列上套函数或做运算、隐式类型转换、返回行比例过大、统计信息过期，都会让优化器放弃索引。解决办法分别是全文检索、表达式索引、统一类型和 `ANALYZE`。

## 最小可运行案例

```sql
EXPLAIN SELECT * FROM orders WHERE lower(code)='abc';  -- Seq Scan
CREATE INDEX idx_lower ON orders(lower(code));
EXPLAIN SELECT * FROM orders WHERE lower(code)='abc';  -- Index Scan
```

## 怎么跑

```powershell
cd "04-能跑快\23-索引失效场景\examples"
uv run python verify.py
```

## 核心 API 速查

| 失效原因 | 解决 |
| --- | --- |
| `LIKE '%x'` | 全文检索 / pg_trgm |
| 列上函数 | 表达式索引 |
| 列上运算 | 表达式索引 |
| 类型不匹配 | 统一类型 |
| 返回比例大 | 正常现象，无需修 |
| 统计过期 | `ANALYZE` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 认为建索引就一定用 | 仍 Seq Scan | 看 EXPLAIN |
| 前置 `%` 搜索 | 全表扫描 | 全文检索 |
| 字符串列传数字比较 | 隐式转换 | 类型对齐 |
| 小表测索引 | Seq Scan 正常 | 造足数据 |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能说出三种索引失效原因
- [ ] 动手题：给 `LIKE '%x'` 建 pg_trgm 索引再测
