# 27 视图与物化视图

## 一句话结论

视图是保存的查询，逻辑上像表但数据实时来自基表；物化视图把结果真实存下来，需要 `REFRESH MATERIALIZED VIEW` 才更新。前者简化查询和权限，后者换性能。

## 最小可运行案例

```sql
CREATE VIEW v_research AS SELECT id,name FROM employee WHERE dept='研发';
CREATE MATERIALIZED VIEW mv AS SELECT dept,count(*) FROM employee GROUP BY dept;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv;  -- 需唯一索引
```

## 怎么跑

```powershell
cd "05-能进生产\27-视图与物化视图\examples"
uv run python verify.py
```

## 核心 API 速查

| 语法 | 作用 |
| --- | --- |
| `CREATE VIEW` | 虚拟表 |
| `CREATE MATERIALIZED VIEW` | 物理结果 |
| `REFRESH MATERIALIZED VIEW` | 刷新 |
| `CONCURRENTLY` | 不锁读 |
| `WITH CHECK OPTION` | 写入须满足条件 |
| `pg_views` / `pg_matviews` | 元数据 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 以为物化视图实时 | 数据过期 | 定期 REFRESH |
| CONCURRENTLY 无唯一索引 | 报错 | 先建唯一索引 |
| 复杂视图期望可更新 | 不可更新 | 用 INSTEAD OF 触发器 |
| 视图套视图太深 | 性能差 | 控制层级 |

## 毕业自查

- [ ] 11/11 通过
- [ ] 能说出两者取舍
- [ ] 动手题：给 mv_dept 加唯一索引后并发刷新
