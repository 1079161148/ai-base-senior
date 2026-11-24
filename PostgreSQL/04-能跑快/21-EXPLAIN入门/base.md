# 21 EXPLAIN 入门 · 完整版

## 0. 怎么用

跑 9/9，再看第 4 节理解 cost 与 actual time。

## 1. 概念

执行计划是优化器对「怎么取数据」的选择，不是 SQL 的文本顺序。

## 2. 机制

```text
SQL → 解析 → 规划器估算 cost → 选最低成本路径 → 执行 → (ANALYZE) 记录真实耗时
```

## 3. API 逐个拆解

| API | 作用 | 注意 |
| --- | --- | --- |
| `EXPLAIN` | 计划 | 不执行 |
| `ANALYZE` | 执行 | 写操作会真的执行 |
| `BUFFERS` | I/O | 需配合 ANALYZE |
| `FORMAT JSON` | 输出格式 | 程序解析用 |
| `ANALYZE 表` | 更新统计 | 与 EXPLAIN ANALYZE 不同 |

## 4. 边界条件

- `cost=0.00..1.05` 是估算单位，不是毫秒。
- 小表即使有索引也可能走 Seq Scan，这是正确的。
- `EXPLAIN ANALYZE UPDATE` 会真的修改数据。

## 5. 注意事项对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 只看 EXPLAIN | 估算失真 | 加 ANALYZE | 实测 |
| 不更新统计 | 计划差 | ANALYZE 表 | 原仓库 06 |
| 小表测索引 | 看不到 Index Scan | 造足数据 | 实测 |
| 把 cost 当毫秒 | 误判 | 看 actual time | 实测 |
| 生产跑 EXPLAIN ANALYZE UPDATE | 真改数据 | 包事务回滚 | 实测 |
| 不看 Buffers | 不知 I/O | 加 BUFFERS | 原仓库 06 |
| 索引建了不验证 | 可能没用上 | EXPLAIN 确认 | 实测 |
| 忽略 seq_page_cost | 理解偏差 | 查 pg_settings | 实测 |
| 计划缓存 | 参数不同计划不同 | 通用计划 vs 定制 | 实测 |
| 不测范围查询 | 只看等值 | 补范围 | 原仓库 06 |
| 用 SELECT * | 影响覆盖索引 | 显式列 | 第 22 章 |
| 不看 rows 估算 | 偏差大 | 对比 actual rows | 实测 |
| 不设统计目标 | 倾斜列估算差 | ALTER COLUMN SET STATISTICS | 实测 |
| 把 Bitmap 当失败 | 它也是索引扫描 | 理解含义 | 实测 |
| 跳过验收 | 不会看计划 | 9/9 再走 | 实测 |
| 不记录计划快照 | 优化无对照 | 存文本 | 实测 |
| 在高峰期 ANALYZE | 加重负载 | 低峰执行 | 实测 |
| 把 ANALYZE 当 Vacuum | 功能不同 | 第 25 章 | 原仓库 07 |

## 6. 最佳实践

任何性能改动前先存一份 `EXPLAIN (ANALYZE, BUFFERS)` 作为基线。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | 原仓库 | 06 索引课件 |

> 本次实测 9/9，2 万行数据，建索引前 Seq Scan，建后 Index Scan。

## 8. 毕业自查

- [ ] 9/9 通过
- [ ] 能读懂一条 EXPLAIN 输出

## 9. 下一章

第 22 章系统学 B-tree 索引与联合索引。
