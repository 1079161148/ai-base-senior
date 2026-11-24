# 16 事务与 ACID

## 一句话结论

事务是一组「要么全成、要么全败」的操作。`BEGIN` 开、`COMMIT` 提交、`ROLLBACK` 撤销、`SAVEPOINT` 设内部检查点。ACID 指原子性、一致性、隔离性、持久性——本章用银行转账和并发连接分别证明。

## 最小可运行案例

```sql
BEGIN;
UPDATE accounts SET balance=balance+100 WHERE id='B';
UPDATE accounts SET balance=balance-100 WHERE id='A';
COMMIT;  -- 或 ROLLBACK
SELECT sum(balance) FROM accounts;  -- 恒为 1500
```

## 怎么跑

```powershell
cd "03-能保证正确\16-事务与ACID\examples"
uv run python verify.py
```

## 核心 API 速查

| 命令 | 作用 |
| --- | --- |
| `BEGIN` | 开事务 |
| `COMMIT` | 提交 |
| `ROLLBACK` | 全回滚 |
| `SAVEPOINT s` | 设检查点 |
| `ROLLBACK TO s` | 回到检查点 |
| `SHOW transaction_isolation` | 查隔离级别 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| autocommit 连接里 ROLLBACK | 无效 | 普通连接 |
| 只转出没转入 | 总额变化 | 一个事务包两步 |
| SAVEPOINT 名重复 | 旧点被覆盖 | 用不同名字 |
| 以为单语句不是事务 |  misunderstood | 单语句自动事务 |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能说出 ACID 四项
- [ ] 动手题：把 COMMIT 改成 ROLLBACK，看余额是否回到 500/1000
