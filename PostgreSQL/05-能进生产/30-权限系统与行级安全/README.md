# 30 权限系统与行级安全

## 一句话结论

`CREATE ROLE` 建角色，`GRANT`/`REVOKE` 控制对象与列级权限；`ROW LEVEL SECURITY` 让不同角色在同一张表里只看到自己的行，是多租户的数据隔离底线。

## 最小可运行案例

```sql
CREATE ROLE app_user LOGIN PASSWORD '...';
GRANT SELECT ON orders TO app_user;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolate ON orders USING (tenant_id = current_tenant());
```

## 怎么跑

```powershell
cd "05-能进生产\30-权限系统与行级安全\examples"
uv run python verify.py
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `CREATE ROLE` | 角色 |
| `GRANT`/`REVOKE` | 授权/回收 |
| `has_table_privilege` | 查权限 |
| `ENABLE ROW LEVEL SECURITY` | 开 RLS |
| `CREATE POLICY` | 定义策略 |
| `SET LOCAL ROLE` | 临时切换角色 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 超级用户测 RLS | 绕过策略 | 用普通角色 |
| 只 GRANT 表不 GRANT schema | 仍不可访问 | 两个都给 |
| RLS 开了无策略 | 默认拒绝所有 | 建策略 |
| 不清理测试角色 | 残留 | DROP OWNED + DROP ROLE |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能写多租户 RLS 策略
- [ ] 动手题：再加一个销售角色，验证只看销售行
