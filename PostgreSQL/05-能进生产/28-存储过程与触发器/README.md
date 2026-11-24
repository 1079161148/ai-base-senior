# 28 存储过程与触发器

## 一句话结论

函数把一段 SQL 逻辑封装成可调用单元；触发器在特定事件（INSERT/UPDATE/DELETE）前后自动执行。自动维护 `updated_at`、写审计日志是触发器的典型用途。

## 最小可运行案例

```sql
CREATE FUNCTION set_updated_at() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END; $$;
CREATE TRIGGER trg BEFORE UPDATE ON items
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

## 怎么跑

```powershell
cd "05-能进生产\28-存储过程与触发器\examples"
uv run python verify.py
```

## 核心 API 速查

| 语法 | 作用 |
| --- | --- |
| `CREATE FUNCTION` | 建函数 |
| `LANGUAGE sql/plpgsql` | 实现语言 |
| `RETURNS SETOF` | 返回行集 |
| `CREATE TRIGGER` | 建触发器 |
| `BEFORE`/`AFTER` | 触发时机 |
| `NEW`/`OLD` | 新行/旧行 |
| `IS DISTINCT FROM` | NULL 安全比较 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| BEFORE 触发器不 RETURN NEW | 行变 NULL | 必须 RETURN |
| 用 `!=` 比较可能为 NULL 的值 | 不触发 | `IS DISTINCT FROM` |
| 触发器递归调用 | 无限循环 | 加条件 |
| 过多触发器 | 写入变慢 | 控制数量 |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能写审计触发器
- [ ] 动手题：把 AFTER 改成 BEFORE，看审计值是否变化
