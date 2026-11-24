# 14 集合运算与窗口函数

## 一句话结论

`UNION` 合并结果并去重，`UNION ALL` 保留重复，`INTERSECT` 取交，`EXCEPT` 取差。窗口函数在不压缩行数的前提下做排名、前后行对比和累计统计，是 `GROUP BY` 之外的另一类分析工具。

## 最小可运行案例

```sql
SELECT id, price,
       row_number() OVER (ORDER BY price) AS rn,
       sum(price) OVER (ORDER BY id) AS acc
FROM skus;
```

## 怎么跑

```powershell
cd "02-能查数\14-集合运算与窗口函数\examples"
uv run python verify.py
```

## 核心 API 速查

| 语法 | 作用 |
| --- | --- |
| `UNION` / `UNION ALL` | 并集（去重/不去重） |
| `INTERSECT` / `EXCEPT` | 交集 / 差集 |
| `row_number()` | 连续序号 |
| `rank()` | 并列跳号 |
| `dense_rank()` | 并列不跳 |
| `lag/lead` | 前一行/后一行 |
| `PARTITION BY` | 窗口分组 |
| `ROWS BETWEEN` | 窗口帧 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| UNION 列数不同 | 报错 | 对齐列数和类型 |
| 以为 UNION 会排序 | 不保证 | 外层 ORDER BY |
| rank 和 row_number 混用 | 并列处理错 | 按需求选 |
| 窗口函数没 ORDER BY | 结果不确定 | 显式排序 |

## 毕业自查

- [ ] 11/11 通过
- [ ] 能说出 rank 与 dense_rank 的区别
- [ ] 动手题：把 `ROWS BETWEEN` 改成 `RANGE BETWEEN`，看累计值是否变化
