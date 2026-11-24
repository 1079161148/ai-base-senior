# 43 embedding批处理与元数据管理

## 一句话结论

批量生成向量时把模型版本、维度、时间戳一起存下来，才能让结果可复现、可增量更新。

## 最小可运行案例

```sql
INSERT INTO docs (title,model,dim,embedding)
VALUES ('文档1','fake-v1',16,'[...]');
```

## 怎么跑

```powershell
cd "06-向量数据库\43-embedding批处理与元数据管理\examples"
uv run python verify.py
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `批量 INSERT` | 高效入库 |
| `model 元数据列` | 记录模型版本 |
| `vector_dims()` | 校验维度 |
| `UPDATE embedding` | 重新 embed |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 不记模型版本 | 向量不可复现 | 存 model 字段 |
| 新旧模型混用 | 空间不一致 | 按版本隔离 |
| 逐条提交 | 慢 | 批量事务 |
| 不校验维度 | 检索报错 | 写入前校验 |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能设计可复现的向量元数据表
