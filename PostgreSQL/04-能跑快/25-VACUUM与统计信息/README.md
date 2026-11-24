# 25 VACUUM 与统计信息

## 一句话结论

PostgreSQL 的 `UPDATE`/`DELETE` 不立即回收空间，而是留下 dead tuples；`VACUUM` 回收它们，`ANALYZE` 更新优化器统计。两者职责不同，autovacuum 默认会自动做。

## 最小可运行案例

```sql
UPDATE churn SET payload='x';
SELECT n_dead_tup FROM pg_stat_user_tables WHERE relname='churn';
VACUUM churn;
ANALYZE churn;
```

## 怎么跑

```powershell
cd "04-能跑快\25-VACUUM与统计信息\examples"
uv run python verify.py
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `VACUUM` | 回收死元组 |
| `VACUUM FULL` | 重写表，锁表 |
| `ANALYZE` | 更新统计 |
| `REINDEX` | 重建索引 |
| `pg_stat_user_tables` | 表统计 |
| `autovacuum` | 自动清理 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 以为 UPDATE 立即释放空间 | 表膨胀 | VACUUM |
| 事务里 VACUUM | 报错 | 事务外执行 |
| VACUUM 当 ANALYZE | 统计没更新 | 两个都做 |
| 频繁 VACUUM FULL | 长时间锁表 | 用普通 VACUUM |

## 毕业自查

- [ ] 9/9 通过
- [ ] 能区分 VACUUM 与 ANALYZE
- [ ] 动手题：连续 UPDATE 10 次，观察 n_dead_tup 变化
