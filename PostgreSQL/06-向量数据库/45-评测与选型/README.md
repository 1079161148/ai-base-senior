# 45 评测与选型

## 一句话结论

用 Recall@k、Precision@k 量化检索效果，再在 IVFFlat/HNSW 与专用向量库之间按规模和需求权衡。

## 最小可运行案例

```sql
-- Recall@3 = 命中相关文档数 / 相关文档总数
SELECT count(*) FROM (...) t;
```

## 怎么跑

```powershell
cd "06-向量数据库\45-评测与选型\examples"
uv run python verify.py
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `Recall@k` | 漏召回率 |
| `Precision@k` | 准确率 |
| `hnsw.ef_search` | 召回调优 |
| `ivfflat.probes` | 召回调优 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 凭感觉调参 | 无依据 | 先建评测集 |
| 只看延迟 | 召回崩了 | 延迟与召回一起看 |
| 小数据谈选型 | 结论失真 | 按真实规模测 |
| 不设基线 | 无法对比 | 先跑暴力检索 |

## 毕业自查

- [ ] 8/8 通过
- [ ] 能设计一个简单的检索评测方案
