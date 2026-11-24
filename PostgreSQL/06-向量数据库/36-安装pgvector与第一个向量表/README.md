# 36 安装pgvector与第一个向量表

## 一句话结论

`CREATE EXTENSION vector` 一次即可给 PostgreSQL 装上向量能力，之后用 `vector(n)` 建列、`<->` 查最近邻，和用普通类型没有区别。

## 最小可运行案例

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE docs (id SERIAL PRIMARY KEY, title TEXT, embedding vector(3));
INSERT INTO docs VALUES (1,'A','[0.1,0.2,0.3]');
SELECT title FROM docs ORDER BY embedding <-> '[0.1,0.2,0.3]'::vector LIMIT 1;
```

## 怎么跑

```powershell
cd "06-向量数据库\36-安装pgvector与第一个向量表\examples"
uv run python verify.py
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `CREATE EXTENSION vector` | 安装扩展 |
| `vector(n)` | 定长向量列 |
| `::vector` | 文本转向量 |
| `<->` | L2 距离 |
| `vector_dims()` | 查维度 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 不建扩展就用 vector | 类型不存在 | 先 CREATE EXTENSION |
| 向量写成 JSON 数组 | 无距离算子 | 用 `[1,2,3]` 字面量 |
| 忘记 `::vector` 强转 | 类型推断失败 | 显式强转 |

## 毕业自查

- [ ] 7/7 通过
- [ ] 能独立建一个向量表并查最近邻
