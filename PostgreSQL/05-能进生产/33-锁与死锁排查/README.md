# 33 锁与死锁排查

## 一句话结论

PostgreSQL 用锁保证并发正确：`pg_locks` 看当前锁，`pg_blocking_pids()` 找阻塞者，`deadlock_timeout` 触发死锁检测并自动回滚一方。行锁记录在元组头而非 `pg_locks`，所以排查阻塞要看等待事件和阻塞 PID，不是找 tuple 锁。

## 最小可运行案例

```sql
SELECT pid, pg_blocking_pids(pid) FROM pg_stat_activity WHERE wait_event_type='Lock';
SELECT locktype, mode, granted FROM pg_locks WHERE relation='accounts'::regclass;
SHOW deadlock_timeout;
```

## 怎么跑

```powershell
cd "05-能进生产\33-锁与死锁排查\examples"
uv run python verify.py
```

## 核心 API 速查

| API / 视图 | 作用 |
| --- | --- |
| `pg_locks` | 当前持有的锁 |
| `pg_stat_activity` | 会话与等待事件 |
| `pg_blocking_pids(pid)` | 谁阻塞了它 |
| `pg_advisory_lock` / `pg_advisory_unlock` | 应用级咨询锁 |
| `deadlock_timeout` | 死锁检测触发间隔 |
| `statement_timeout` | 单语句超时，防永久阻塞 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 在 pg_locks 找元组锁 | 找不到 | 行锁在元组头，看等待事件 |
| 不加 statement_timeout 就等锁 | 线程永久挂起 | 设超时兜底 |
| 长事务持锁不提交 | 全表阻塞 | 缩短事务，及时 commit |
| 乱用咨询锁不释放 | 会话结束才释放 | 配对 unlock |
| 死锁后重试同一事务 | 再次死锁 | 加随机退避重试 |

## 毕业自查

- [ ] 12/12 通过
- [ ] 能说出 `pg_blocking_pids()` 的用法
- [ ] 动手题：把 `deadlock_timeout` 调大，观察检测变慢
