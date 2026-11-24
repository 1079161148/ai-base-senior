# 13 子查询与 CTE

## 一句话结论

子查询按返回形态分标量（一个值）、行（一行多列）、表（多行多列）；`EXISTS` 只关心「有没有」，通常比 `IN` 更稳；CTE（`WITH`）把复杂查询拆成可命名的小块，递归 CTE 能查树形结构。

## 最小可运行案例

```sql
WITH RECURSIVE t AS (
  SELECT id, parent_id, 1 AS depth FROM tree WHERE parent_id IS NULL
  UNION ALL
  SELECT c.id, c.parent_id, t.depth+1 FROM tree c JOIN t ON c.parent_id=t.id
)
SELECT * FROM t;
```

## 怎么跑

```powershell
cd "02-能查数\13-子查询与CTE\examples"
uv run python verify.py
```

## 核心 API 速查

| 语法 | 作用 |
| --- | --- |
| `(SELECT ...)` | 标量/行子查询 |
| `IN (SELECT ...)` | 集合成员判断 |
| `EXISTS (SELECT 1 ...)` | 存在性判断 |
| `WITH x AS (...)` | CTE |
| `WITH RECURSIVE` | 递归 CTE |
| `MATERIALIZED` | 强制物化 CTE |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `NOT IN` 子查询含 NULL | 返回空集 | `NOT EXISTS` |
| 标量子查询返回多行 | 运行时报错 | 加 LIMIT 或聚合 |
| 递归 CTE 缺终止条件 | 无限递归 | 必须有 anchor |
| CTE 里写 ORDER BY | 可能被优化掉 | 外层排序 |

## 毕业自查

- [ ] 12/12 通过
- [ ] 能解释 NOT IN 的 NULL 陷阱
- [ ] 动手题：给递归 CTE 加一个环，观察是否无限递归
