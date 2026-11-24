# 10 排序、分页与去重

## 一句话结论

`ORDER BY` 决定顺序，`LIMIT/OFFSET` 决定取哪一段，`DISTINCT` 决定去重粒度。PostgreSQL 特有 `DISTINCT ON (列)` 能「每组取第一行」，常用来取每组最新记录。分页**必须配 ORDER BY**，否则每次顺序可能不同。

## 最小可运行案例

```sql
SELECT id, name FROM products ORDER BY id LIMIT 3 OFFSET 3;
SELECT DISTINCT ON (category_id) category_id, id, name
FROM products ORDER BY category_id, id;
```

## 怎么跑

```powershell
cd "02-能查数\10-排序分页与去重\examples"
uv run python verify.py
```

## 核心 API 速查

| 语法 | 作用 |
| --- | --- |
| `ORDER BY ... ASC/DESC` | 排序 |
| `NULLS FIRST/LAST` | 控制 NULL 位置 |
| `LIMIT n OFFSET m` | 分页 |
| `DISTINCT` | 整行去重 |
| `DISTINCT ON (col)` | 每组取一行 | 
| `ORDER BY 1` | 按第 1 列排序 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 分页不排序 | 页间重复/漏行 | 必加 ORDER BY |
| `DISTINCT` 后 ORDER BY 非选中列 | 报错 | 把列放进 SELECT |
| 以为 NULL 总排最后 | PG 默认 NULLS LAST（升序） | 显式写更稳 |
| `LIMIT 2,3` | PG 非标准写法 | `LIMIT 3 OFFSET 2` |

## 毕业自查

- [ ] 11/11 通过
- [ ] 能解释 DISTINCT ON 为什么要配 ORDER BY
- [ ] 动手题：把分页的 ORDER BY 去掉，多跑几次看顺序是否稳定
