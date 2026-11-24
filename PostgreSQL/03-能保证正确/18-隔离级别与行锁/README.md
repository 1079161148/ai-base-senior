# 18 隔离级别与行锁

## 一句话结论

隔离级别控制「看到什么」，`FOR UPDATE` 控制「谁能改」。抢购扣库存的正确做法是事务里 `SELECT ... FOR UPDATE` 锁住行再改；`NOWAIT` 立即失败，`SKIP LOCKED` 跳过被锁行，适合任务队列。

## 最小可运行案例

```sql
BEGIN;
SELECT qty FROM stock WHERE id=1 FOR UPDATE;  -- 锁住这一行
UPDATE stock SET qty=qty-1 WHERE id=1;
COMMIT;
```

## 怎么跑

```powershell
cd "03-能保证正确\18-隔离级别与行锁\examples"
uv run python verify.py
```

## 核心 API 速查

| 语法 | 作用 |
| --- | --- |
| `SET TRANSACTION ISOLATION LEVEL` | 本次事务隔离 |
| `SET SESSION CHARACTERISTICS` | 会话默认 |
| `FOR UPDATE` | 排他行锁 |
| `FOR SHARE` | 共享行锁 |
| `FOR UPDATE NOWAIT` | 拿不到立即报错 |
| `FOR UPDATE SKIP LOCKED` | 跳过已锁行 |
| `pg_locks` | 锁元数据 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 先 UPDATE 再判断库存 | 超卖 | 先 FOR UPDATE |
| NOWAIT 不捕获异常 | 应用崩溃 | catch LockNotAvailable |
| SKIP LOCKED 当普通查询 | 漏行 | 明确场景 |
| 会话隔离级别忘了还原 | 后续事务受影响 | 用后恢复 |

## 毕业自查

- [ ] 9/9 通过
- [ ] 能解释 NOWAIT 与 SKIP LOCKED 的适用场景
- [ ] 动手题：去掉 FOR UPDATE 重跑超卖用例
