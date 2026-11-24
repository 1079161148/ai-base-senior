# 21 EXPLAIN 入门

## 一句话结论

`EXPLAIN` 显示优化器**打算怎么做**，`EXPLAIN ANALYZE` 才真的执行并显示耗时，`BUFFERS` 看 I/O。优化前后必须看计划，不能凭感觉。

## 最小可运行案例

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM orders WHERE created_at >= '2024-06-01' AND created_at < '2024-07-01';
```

## 怎么跑

```powershell
cd "04-能跑快\21-EXPLAIN入门\examples"
uv run python verify.py
```

## 核心 API 速查

| 选项 | 作用 |
| --- | --- |
| `EXPLAIN` | 只出计划 |
| `ANALYZE` | 真执行、出真实耗时 |
| `BUFFERS` | 缓冲区读写 |
| `FORMAT JSON` | 机器可读 |
| `Seq Scan` | 全表扫描 |
| `Index Scan` | 索引扫描 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 只 EXPLAIN 不看 ANALYZE | 估算可能失真 | 加 ANALYZE |
| 不 ANALYZE 表就测 | 统计信息旧 | 先 ANALYZE |
| 小表上测索引 | 优化器选 Seq Scan | 用足够数据 |
| 把 cost 当毫秒 | 单位不同 | 看 actual time |

## 毕业自查

- [ ] 9/9 通过
- [ ] 能区分 Seq Scan 与 Index Scan
- [ ] 动手题：删索引后重跑，确认计划变回 Seq Scan
