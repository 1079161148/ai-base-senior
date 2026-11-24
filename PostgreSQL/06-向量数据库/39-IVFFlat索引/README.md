# 39 IVFFlat索引

## 一句话结论

IVFFlat 把向量分成 lists 个聚类，查询只探查 probes 个桶，用少量精度换取大幅提速。

## 最小可运行案例

```sql
CREATE INDEX ON docs USING ivfflat (embedding vector_l2_ops) WITH (lists=10);
SET ivfflat.probes=5;
SELECT * FROM docs ORDER BY embedding <-> '[0,0,0]'::vector LIMIT 10;
```

## 怎么跑

```powershell
cd "06-向量数据库\39-IVFFlat索引\examples"
uv run python verify.py
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `USING ivfflat` | 倒排索引方法 |
| `lists` | 聚类数 |
| `ivfflat.probes` | 查询探查桶数 |
| `vector_l2_ops` | L2 算子类 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 数据太少建索引 | 无收益 | 万行以上再建 |
| lists 过大 | 每桶太小 | 约按 sqrt(n) 取值 |
| probes 过小 | 召回下降 | 调大 probes |
| 先建索引后灌数 | 聚类质量差 | 灌数后再建 |

## 毕业自查

- [ ] 7/7 通过
- [ ] 能解释 lists 与 probes 的权衡
