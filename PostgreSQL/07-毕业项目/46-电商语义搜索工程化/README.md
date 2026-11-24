# 46 电商语义搜索工程化

## 一句话结论

毕业项目把 47 章能力串成一条链：用 M01/M02 的电商库建模与查询，M03 的事务保证一致性，M05 的视图/权限/物化视图做工程化，M06 的 pgvector 做语义检索与混合召回，最后用评测与索引收口。

## 最小可运行案例

```sql
ALTER TABLE products ADD COLUMN embedding vector(16);
UPDATE products SET embedding='[...]' WHERE id=1;
SELECT name FROM products
ORDER BY embedding <=> '[查询向量]'::vector LIMIT 5;
```

## 怎么跑

```powershell
cd "07-毕业项目\46-电商语义搜索工程化\examples"
uv run python verify.py
```

## 项目结构

| 环节 | 用到的章 | 本章实现 |
| --- | --- | --- |
| 电商库建模 | 03–07、34 | setup_shop 四表关系 |
| 商品向量化 | 35、43 | embedding + model 元数据 |
| 语义检索 | 38、41 | Top-K + 类目过滤 |
| 混合召回 | 42 | RRF 融合 |
| 索引加速 | 39、40 | HNSW + B-tree |
| 汇总视图 | 27 | 物化视图统计 |
| 权限隔离 | 30 | 只读角色 |
| 事务一致 | 16–19 | 回滚验证 |
| 评测 | 45 | Recall/子集校验 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| RRF 用整数 1/(60+rank) | 分数恒为 0 | 用 1.0 |
| 向量化不记模型 | 无法复现 | 存 model 列 |
| 检索不过滤类目 | 跨类噪声 | 加元数据 WHERE |
| 灌数前建索引 | 索引质量差 | 先数据后索引 |
| 无评测 | 效果未知 | 固定评测集 |

## 毕业自查

- [ ] 13/13 通过
- [ ] 能独立复述整条工程链
- [ ] 动手题：把 HNSW 换成 IVFFlat 并对比召回
