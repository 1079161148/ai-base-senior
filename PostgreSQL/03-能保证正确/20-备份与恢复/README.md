# 20 备份与恢复

## 一句话结论

最小备份是 `CREATE TABLE ... AS TABLE`（结构+数据快照）；跨库用 `COPY ... TO STDOUT WITH CSV` 导出、`COPY ... FROM STDIN` 导入；生产环境用 `pg_dump`/`pg_restore`。PostgreSQL 的 `TRUNCATE` 和 `CREATE TABLE` 都能在事务里回滚。

## 最小可运行案例

```sql
CREATE TABLE backup AS TABLE src;
DELETE FROM src;
INSERT INTO src SELECT * FROM backup;
```

```powershell
docker exec pg16-study pg_dump -U admin -d study -n ch20 -f /tmp/ch20.sql
```

## 怎么跑

```powershell
cd "03-能保证正确\20-备份与恢复\examples"
uv run python verify.py
```

## 核心 API 速查

| 命令 | 作用 |
| --- | --- |
| `CREATE TABLE AS TABLE` | 同库快照 |
| `COPY ... TO STDOUT WITH CSV` | 导出 |
| `COPY ... FROM STDIN WITH CSV` | 导入 |
| `pg_dump` | 逻辑备份（命令行） |
| `pg_restore` | 恢复（命令行） |
| `TRUNCATE ... ROLLBACK` | PG 中可回滚 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 只备份数据不备份结构 | 恢复时无表 | 用 pg_dump |
| 备份不记时间点 | 不知恢复到哪 | 记 timestamp |
| 以为 TRUNCATE 不可回滚 | 误区 | PG 可回滚 |
| 生产直接 CTAS 大表 | 锁时间长 | 用 pg_dump 或复制槽 |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能说出 CTAS 与 pg_dump 的差别
- [ ] 动手题：把备份表删掉再跑恢复，观察失败
