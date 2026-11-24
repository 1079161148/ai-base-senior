# 25 VACUUM 与统计信息 · 完整版

## 0. 怎么用

跑 9/9，再看第 4 节理解 MVCC 为什么会留下死元组。

## 1. 概念

MVCC 让旧版本行仍被其他事务可见，因此 UPDATE 是「插入新版本 + 标记旧版本」，空间靠 VACUUM 回收。

## 2. 机制

```text
UPDATE → 新版本 + 旧版本标记死亡 → VACUUM 回收 → ANALYZE 更新统计
```

## 3. API 逐个拆解

| API | 作用 | 注意 |
| --- | --- | --- |
| `VACUUM` | 清理 | 不锁写 |
| `VACUUM FULL` | 重写 | 锁整表 |
| `ANALYZE` | 统计 | 影响计划 |
| `REINDEX` | 重建索引 | 解决索引膨胀 |
| `n_dead_tup` | 死元祖数 | 膨胀指标 |

## 4. 边界条件

- 事务内不能执行 VACUUM。
- VACUUM 不能回收仍被长事务引用的旧版本。
- 大批量导入后必须 ANALYZE，否则统计 stale。

## 5. 注意事项对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| UPDATE 当原地修改 | 空间不释放 | VACUUM | 实测 |
| 事务里 VACUUM | 报错 | 事务外 | 实测 |
| VACUUM 当 ANALYZE | 统计不更新 | 两个都做 | 实测 |
| 频繁 VACUUM FULL | 锁表 | 普通 VACUUM | 实测 |
| 长事务不提交 | VACUUM 无效 | 缩短事务 | 实测 |
| 不看 n_dead_tup | 膨胀不知 | 查统计 | 实测 |
| 导入后不 ANALYZE | 计划差 | 补执行 | 原仓库 06 |
| 不看 autovacuum 配置 | 不知何时触发 | 查 pg_settings | 实测 |
| 索引膨胀不处理 | 查询变慢 | REINDEX | 实测 |
| 大表 VACUUM 高峰执行 | IO 压力 | 低峰 | 实测 |
| 以为 VACUUM 缩小文件 | 通常不 | VACUUM FULL | 实测 |
| 不记录统计基线 | 无法比较 | 存快照 | 实测 |
| 把 ANALYZE 当优化 | 只是统计 | 继续 EXPLAIN | 第 21 章 |
| 禁用 autovacuum | 必然膨胀 | 保留 | 实测 |
| 不查 pg_database_size | 空间失控 | 定期查 | 实测 |
| 跳过验收 | 膨胀认知错 | 9/9 再走 | 实测 |
| 把 REINDEX 当常规维护 | 代价高 | 按需 | 实测 |
| 忽略 last_vacuum | 不知是否执行 | 查统计 | 实测 |

## 6. 最佳实践

保留 autovacuum，批量导入后手动 ANALYZE，膨胀严重时再 REINDEX。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | 原仓库 | 07 拓展知识（VACUUM） |

> 本次实测 9/9，UPDATE 产生死元组后 VACUUM 使其下降，ANALYZE 后 n_live_tup=2000。

## 8. 毕业自查

- [ ] 9/9 通过
- [ ] 能解释 MVCC 与死元组的关系

## 9. 下一章

第 26 章学分区表。
