# 41 TopK阈值与元数据过滤

## 一句话结论

真实检索是 ORDER BY 距离 LIMIT k 加 WHERE 元数据条件，必要时再用距离阈值过滤低质结果。

## 最小可运行案例

```sql
SELECT name FROM products
WHERE category='数码' AND embedding <-> '[1,0,0]'::vector < 0.5
ORDER BY embedding <-> '[1,0,0]'::vector LIMIT 5;
```

## 怎么跑

```powershell
cd "06-向量数据库\41-TopK阈值与元数据过滤\examples"
uv run python verify.py
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `LIMIT k` | Top-K |
| `WHERE 距离 < 阈值` | 质量控制 |
| `WHERE 元数据列` | 结构化过滤 |
| `1/(1+距离)` | 相似度分数 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 无 LIMIT | 全表排序 | 始终限制 k |
| 阈值拍脑袋 | 过滤过度或不足 | 用评测校准 |
| 先过滤再排序搞反 | 结果错 | WHERE 在前 ORDER 在后 |
| 元数据不建索引 | 过滤慢 | 补 B-tree |

## 毕业自查

- [ ] 7/7 通过
- [ ] 能组合元数据与向量条件写查询
