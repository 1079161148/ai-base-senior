# 42 混合检索

## 一句话结论

关键词检索保证精确匹配、向量检索保证语义相近，用 RRF 融合两路排名可取长补短。

## 最小可运行案例

```sql
SELECT id, 1/(60+kw_rank)+1/(60+vec_rank) AS score
FROM hybrid ORDER BY score DESC;
```

## 怎么跑

```powershell
cd "06-向量数据库\42-混合检索\examples"
uv run python verify.py
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `ILIKE / to_tsvector` | 关键词检索 |
| `<=>` | 向量检索 |
| `RRF 1/(60+rank)` | 排名融合 |
| `GIN + HNSW` | 两路索引 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 中文用 simple 分词 | 词命中差 | ILIKE 或中文分词插件 |
| 只做向量检索 | 精确词漏召回 | 加关键词路 |
| 分数直接相加 | 量纲不同 | 用 RRF 按排名融合 |
| 不建 GIN | 关键词慢 | 建 GIN 索引 |

## 毕业自查

- [ ] 7/7 通过
- [ ] 能解释 RRF 为什么按排名而非分数融合
