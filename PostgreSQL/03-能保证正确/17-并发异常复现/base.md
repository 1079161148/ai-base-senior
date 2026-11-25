# 17 并发异常复现 · 完整版

## 0. 怎么用

跑 9/9，再看第 4 节理解与常见说法的差异。

## 1. 概念

隔离级别是「并发事务之间能看到多少」的契约。级别越高越安全，吞吐越低。

## 2. 机制

```text
READ COMMITTED     → 每条语句一个快照
REPEATABLE READ    → 事务级快照
SERIALIZABLE       → 快照 + 冲突检测（SSI）
```

## 3. API 逐个拆解

| API | 作用 | 注意 |
| --- | --- | --- |
| `SET TRANSACTION ISOLATION LEVEL` | 设置本次事务隔离 | 必须在 BEGIN 后、语句前 |
| `default_transaction_isolation` | 会话默认 | 可 SET 会话级 |
| `SerializationFailure` | 冲突异常 | 应用需重试 |
| `pg_backend_pid()` | 连接标识 | 多连接排查 |

## 4. 边界条件

- PostgreSQL 没有 `READ UNCOMMITTED`，设置后按 `READ COMMITTED` 处理。
- 很多资料说 RR 可能更新丢失，但 PG 的 RR 在写冲突时抛 `SerializationFailure`，不会静默丢失。
- 幻读在 PG 的 RR 下被快照挡住，这是 MVCC 实现决定的。

## 5. 注意事项对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 单连接模拟并发 | 测不出 | 两连接 | 实测 |
| autocommit 里 BEGIN | 无效 | 普通连接 | 实测 |
| 照搬二手资料 RR 表格 | 与 PG 不符 | 以实测为准 | 实测 |
| 冲突后不回滚 | 连接异常 | ROLLBACK | 实测 |
| SET 隔离级别太晚 | 报错 | BEGIN 后立即设 | 实测 |
| 不关闭连接 | 占连接数 | 显式 close | 实测 |
| 用 SERIALIZABLE 做所有事 | 吞吐低 | 按需升级 | 通用实践 |
| 不测脏读 | 不知道 PG 已挡 | 补用例 | 实测 |
| 以为幻读只在 SERIALIZABLE 发生 | 错误 | RC 也会 | 实测 |
| 不记录连接 pid | 排查困难 | 记录 | 实测 |
| 并发测试不清理数据 | 后续用例受影响 | 每章独立 schema | 实测 |
| 把隔离当锁 | 概念混 | 分清机制 | 通用实践 |
| 不处理 SerializationFailure | 应用崩溃 | 重试 | 实测 |
| 长事务升 SERIALIZABLE | 冲突率高 | 缩短事务 | 实测 |
| 不查默认隔离 | 靠猜 | SHOW | 实测 |
| 跳过验收 | 并发认知错 | 9/9 再走 | 实测 |
| 用 READ UNCOMMITTED | 被降级 | 别用 | 通用实践 |
| 把更新丢失当幻读 | 概念混淆 | 分清读写 | 实测 |

## 6. 最佳实践

默认 `READ COMMITTED`；需要事务内一致读时用 RR；写冲突频繁时加版本号或重试 SERIALIZABLE。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | 官方文档 | PostgreSQL 16 官方手册 |

> 本次实测 9/9。与常见说法的差异：PG 的 RR 会抛 `SerializationFailure` 阻止更新丢失，不是静默丢失。

## 8. 毕业自查

- [ ] 8/8 通过
- [ ] 能说出四级隔离差异

## 9. 下一章

第 18 章学隔离级别选型与 `FOR UPDATE` 行锁。
