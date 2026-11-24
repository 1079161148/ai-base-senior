# 15 电商 33 题实战

## 一句话结论

原仓库 `04. DML/课件.md` 末尾给了 33 道电商查询题。本章用简化数据集逐条实现，覆盖条件过滤、聚合分组、四种 JOIN、子查询、NOT EXISTS、日期截断和排序分页。33/33 全绿，说明 M02「能查数」这一关过了。

## 最小可运行案例

```sql
SELECT count(*) FROM products p
WHERE NOT EXISTS (
  SELECT 1 FROM skus s JOIN order_items oi ON s.id=oi.sku_id
  WHERE s.product_id=p.id
);
-- 第 25 题：从未被购买过的商品
```

## 怎么跑

```powershell
cd "02-能查数\15-电商33题实战\examples"
uv run python verify.py
```

## 核心 API 速查

| 题号区间 | 主要知识点 |
| --- | --- |
| 01–11 | `SELECT`/`WHERE`/`ORDER BY`/`LIMIT` |
| 12–20 | 聚合、`GROUP BY`、`HAVING` |
| 21–23 | `JOIN` 与分页 |
| 24–29 | 子查询、`EXISTS`、分组排序 |
| 30–33 | `date_trunc` 日期分组、`LIKE`、Top-N |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 用 `NOT IN` 找未购买商品 | NULL 陷阱 | `NOT EXISTS` |
| 分组后忘记 `HAVING` | 条件写错位置 | 区分 WHERE/HAVING |
| `date_trunc` 后不 GROUP BY | 报错 | 加分组 |
| Top-N 不排序 | 结果随机 | 明确 ORDER BY |

## 毕业自查

- [ ] 33/33 通过
- [ ] 能独立写出 10 道题
- [ ] 动手题：给第 25 题改用 LEFT JOIN + IS NULL，结果应一致
