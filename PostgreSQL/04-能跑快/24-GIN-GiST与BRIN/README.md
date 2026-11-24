# 24 GIN、GiST 与 BRIN

## 一句话结论

B-tree 管标量和范围，GIN 管 JSONB/数组/全文检索的多值包含，GiST 管几何与范围类型，BRIN 为物理有序的超大表提供极小索引。选错索引方法，查询照样全表扫。

## 最小可运行案例

```sql
CREATE INDEX idx_attrs ON products USING gin (attrs);
SELECT * FROM products WHERE attrs @> '{"brand":"华为"}';

CREATE INDEX idx_vec_search ON docs USING gin (search_vector);
SELECT * FROM docs WHERE search_vector @@ plainto_tsquery('中文','数据库');
```

## 怎么跑

```powershell
cd "04-能跑快\24-GIN-GiST与BRIN\examples"
uv run python verify.py
```

## 核心 API 速查

| 索引 | 适用 |
| --- | --- |
| GIN | JSONB、数组、tsvector |
| GiST | 范围、几何、最近邻 |
| BRIN | 物理有序大表 |
| `@>` | 包含 |
| `@@` | 全文匹配 |
| `to_tsvector` | 文档向量 |
| `ts_rank` | 相关性排序 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 用 B-tree 查 JSONB | 用不上索引 | GIN |
| 表数据乱序建 BRIN | 几乎无效果 | 按序物理存储 |
| 全文检索不做分词 | 查不到 | to_tsvector |
| 以为 GIN 越小越好 | GIN 通常较大 | 按场景选 |

## 毕业自查

- [ ] 9/9 通过
- [ ] 能说出四种索引方法各适合什么
- [ ] 动手题：删掉 GIN 索引，对比查询计划
