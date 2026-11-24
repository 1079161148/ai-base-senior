# 37 vector类型与维度

## 一句话结论

vector(n) 把维度写进类型，插入不同维度会被直接拒绝；vector 不加 n 则维度自由但无法建索引。

## 最小可运行案例

```sql
CREATE TABLE v (embedding vector(3));
INSERT INTO v VALUES ('[1,2,3]');  -- 合法
INSERT INTO v VALUES ('[1,2]');     -- 报错：维度不符
```

## 怎么跑

```powershell
cd "06-向量数据库\37-vector类型与维度\examples"
uv run python verify.py
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `vector(n)` | 定长向量类型 |
| `vector` | 变长向量，不可建索引 |
| `vector_dims()` | 查询维度 |
| `::real[]` | 转数组 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 改维度不重建列 | 旧数据不兼容 | 重建列并重新 embed |
| 变长 vector 建索引 | 报错 | 用定长 vector(n) |
| 维度与模型不符 | 结果无意义 | 维度绑定模型 |

## 毕业自查

- [ ] 7/7 通过
- [ ] 能说出定长与变长 vector 的区别
