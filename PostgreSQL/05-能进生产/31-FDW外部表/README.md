# 31 FDW 外部表

## 一句话结论

FDW（Foreign Data Wrapper）把外部数据源映射成本地表，查询时数据库自动去远端取数。`postgres_fdw` 用于跨 PostgreSQL 实例，`file_fdw` 可读 CSV。适合临时数据整合和迁移，不适合高频联表。

## 最小可运行案例

```sql
CREATE EXTENSION postgres_fdw;
CREATE SERVER remote FOREIGN DATA WRAPPER postgres_fdw
  OPTIONS (host '127.0.0.1', port '5432', dbname 'other');
CREATE USER MAPPING FOR current_user SERVER remote
  OPTIONS (user 'u', password 'p');
CREATE FOREIGN TABLE t (id int) SERVER remote OPTIONS (schema_name 'public', table_name 't');
SELECT * FROM t;
```

## 怎么跑

```powershell
cd "05-能进生产\31-FDW外部表\examples"
uv run python verify.py
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `CREATE EXTENSION postgres_fdw` | 装扩展 |
| `CREATE SERVER` | 定义远端 |
| `CREATE USER MAPPING` | 认证映射 |
| `CREATE FOREIGN TABLE` | 映射表 |
| `IMPORT FOREIGN SCHEMA` | 批量导入定义 |
| `postgres_fdw_get_connections()` | 查连接 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 密码写死在脚本 | 泄露 | 用环境变量 |
| 外部表无本地统计 | 计划差 | ANALYZE |
| 高频 JOIN 外部表 | 慢 | 先同步到本地 |
| 忘 DROP SERVER | 残留对象 | 按顺序清理 |

## 毕业自查

- [ ] 9/9 通过
- [ ] 能说出 FDW 的适用场景
- [ ] 动手题：把外部表 JOIN 改成先 COPY 到本地再 JOIN，对比耗时
