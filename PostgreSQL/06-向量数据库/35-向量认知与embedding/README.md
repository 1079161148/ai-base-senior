# 35 向量认知与embedding

## 一句话结论

向量数据库存的是"语义坐标"：embedding 模型把文本变成一组数字，语义相近的文本坐标也相近，于是相似度搜索变成"找距离最近的向量"。pgvector 让 PostgreSQL 直接具备这个能力，不用另起一套数据库。

## 最小可运行案例

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE docs (id SERIAL PRIMARY KEY, title TEXT, embedding vector(8));
SELECT title FROM docs ORDER BY embedding <-> '[0.1,0.2,...]'::vector LIMIT 5;
```

## 怎么跑

```powershell
cd "06-向量数据库\35-向量认知与embedding\examples"
uv run python verify.py
```

## 关键概念

| 概念 | 含义 |
| --- | --- |
| embedding | 文本/图片 → 高维向量的映射 |
| 向量维度 | 坐标数量，需与模型一致 |
| 距离 | L2 / 余弦 / 内积，衡量语义远近 |
| kNN | 找距离最近的 k 个点 |
| pgvector | PostgreSQL 的向量类型 + 索引 + 算子 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 换模型不改维度 | 插入报维度不符 | 维度与模型绑定 |
| 用欧氏距离比归一化向量 | 排序偏差 | 余弦距离更稳 |
| 以为向量能"理解"语义 | 模型决定上限 | 选对 embedding 模型 |
| 教学用随机向量 | 相似度无意义 | 用可复现向量验证机制 |

## 毕业自查

- [ ] 7/7 通过
- [ ] 能说清 embedding 与 kNN 的关系
- [ ] 动手题：把 dim 改成 16，观察距离变化
