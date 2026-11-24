# 44 RAG最小闭环

## 一句话结论

RAG 就是把文档切块存向量、检索 Top-K 块、拼进提示词；pgvector 承担中间的检索环节。

## 最小可运行案例

```sql
SELECT doc_id,chunk_no,content
FROM chunks ORDER BY embedding <=> '[query]'::vector LIMIT 3;
```

## 怎么跑

```powershell
cd "06-向量数据库\44-RAG最小闭环\examples"
uv run python verify.py
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `切块 chunk` | 文档分段 |
| `<=>` | 块检索 |
| `LIMIT k` | 取上下文 |
| `拼 context` | 送入大模型 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 块太大 | 噪声多 | 合理分块 |
| 块太小 | 语义断裂 | 保留重叠 |
| 不按 doc 过滤 | 跨文档串味 | 加 doc_id 条件 |
| 无索引 | 量大变慢 | 建 HNSW |

## 毕业自查

- [ ] 8/8 通过
- [ ] 能画出 RAG 的数据流
