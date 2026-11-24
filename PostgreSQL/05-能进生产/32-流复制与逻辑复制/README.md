# 32 流复制与逻辑复制

## 一句话结论

流复制同步整个实例（物理级，用于高可用），逻辑复制按表同步变更（可跨版本、可选表）。两者都依赖 WAL；复制槽保证主库不提前回收还没被消费的 WAL。本章用 `test_decoding` 真读一次逻辑变更。

## 最小可运行案例

```sql
SELECT pg_create_logical_replication_slot('my_slot','test_decoding');
INSERT INTO orders ...;
SELECT data FROM pg_logical_slot_peek_changes('my_slot', NULL, 10);
SELECT pg_drop_replication_slot('my_slot');
```

## 怎么跑

```powershell
cd "05-能进生产\32-流复制与逻辑复制\examples"
uv run python verify.py
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `wal_level` | WAL 详细程度 |
| `pg_current_wal_lsn()` | 当前位置 |
| `pg_stat_replication` | 从库状态 |
| `CREATE PUBLICATION` | 发布表 |
| `pg_create_logical_replication_slot` | 建槽 |
| `pg_logical_slot_peek_changes` | 读变更 |
| `pg_drop_replication_slot` | 删槽 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 槽不删 | WAL 无限堆积 | 用完 DROP |
| wal_level=minimal 做逻辑复制 | 不支持 | 改 logical |
| 用 peek 当消费 | 不推进位置 | 用 get_changes |
| 把逻辑复制当备份 | 不保留全量 | 配合 pg_dump |

## 毕业自查

- [ ] 11/11 通过
- [ ] 能说出流复制与逻辑复制的差别
- [ ] 动手题：把 peek 改成 get_changes，观察槽位置推进
