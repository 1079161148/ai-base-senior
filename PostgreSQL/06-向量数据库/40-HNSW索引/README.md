# 40 HNSW索引

## 一句话结论

HNSW 用多层近邻图实现近似检索，召回通常优于 IVFFlat，构建更慢、内存更高。

## 最小可运行案例

```sql
CREATE INDEX ON docs USING hnsw (embedding vector_cosine_ops)
  WITH (m=16, ef_construction=64);
SET hnsw.ef_search=40;
```

## 怎么跑

```powershell
cd "06-向量数据库\40-HNSW索引\examples"
uv run python verify.py
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `USING hnsw` | 图索引方法 |
| `m` | 每层连接数 |
| `ef_construction` | 构建时候选数 |
| `hnsw.ef_search` | 查询时候选数 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| ef_search 过小 | 召回低 | 调大 |
| 高维 + 大 m | 内存爆 | 权衡 m |
| 频繁更新 | 图维护贵 | 批量更新 |
| 不评测就上线 | 效果未知 | 第 45 章 |

## 毕业自查

- [ ] 7/7 通过
- [ ] 能说出 HNSW 与 IVFFlat 的取舍
