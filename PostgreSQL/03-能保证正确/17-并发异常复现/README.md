# 17 并发异常复现

## 一句话结论

用两个独立连接交错执行，能看到真实行为：**PG 不会发生脏读**；`READ COMMITTED` 下会发生不可重复读、幻读和更新丢失；升到 `REPEATABLE READ` 后前两种被挡住；`SERIALIZABLE` 连并发写冲突也会抛错回滚。这与常见资料里「RR 可能发生更新丢失」的说法有差异——以实测为准。

## 最小可运行案例

```sql
-- 连接 A
BEGIN;
SELECT balance FROM accounts WHERE id='A';  -- 1000
-- 连接 B 更新并提交
UPDATE accounts SET balance=800 WHERE id='A'; COMMIT;
-- 连接 A 再读
SELECT balance FROM accounts WHERE id='A';  -- READ COMMITTED 下变成 800
COMMIT;
```

## 怎么跑

```powershell
cd "03-能保证正确\17-并发异常复现\examples"
uv run python verify.py
```

## 核心 API 速查

| 异常 | READ COMMITTED | REPEATABLE READ | SERIALIZABLE |
| --- | --- | --- | --- |
| 脏读 | 不发生 | 不发生 | 不发生 |
| 不可重复读 | 发生 | 不发生 | 不发生 |
| 幻读 | 发生 | 不发生 | 不发生 |
| 更新丢失 | 发生 | PG 抛错 | PG 抛错 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 用同一连接模拟两个事务 | 测不出并发 | 两个独立连接 |
| autocommit 下 BEGIN | 不生效 | 普通连接 |
| 把二手资料表格当 PG 实测 | RR 差异 | 以实测为准 |
| 不回滚冲突事务 | 连接状态异常 | catch 后 ROLLBACK |

## 毕业自查

- [ ] 8/8 通过
- [ ] 能解释为什么 PG 没有脏读
- [ ] 动手题：把隔离级别改成 SERIALIZABLE 重跑不可重复读用例
