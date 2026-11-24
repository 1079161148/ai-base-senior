# 04 CREATE 类型与约束

## 一句话结论

`CREATE TABLE` 一次声明三类信息：**列类型**（`SERIAL`/`NUMERIC`/`UUID`/`JSONB`）、**列约束**（`NOT NULL`/`UNIQUE`/`CHECK`/`DEFAULT`）、**表约束**（单列或复合 `PRIMARY KEY`）。这一章用 13 条断言建出原仓库的 `students` 表，并真实验证约束会拒绝坏数据。

## 最小可运行案例

```sql
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    age INTEGER CHECK (age > 0),
    score NUMERIC(5,2) DEFAULT 0.00,
    email VARCHAR(100) UNIQUE,
    uid UUID DEFAULT gen_random_uuid()
);
INSERT INTO students (name, age, email) VALUES ('张三', 22, 'z@example.com');
```

## 怎么跑

```powershell
cd "01-能建表\04-CREATE类型与约束\examples"
uv run python verify.py    # 结果：13/13 通过
```

## 核心 API 速查

| 类型/约束 | 作用 | 注意 |
| --- | --- | --- |
| `SERIAL` | 自增整数 | 底层是 sequence |
| `NUMERIC(m,n)` | 精确小数 | 金额必须用 |
| `TIMESTAMPTZ` | 带时区时间 | 优先于 `TIMESTAMP` |
| `UUID` | 通用唯一标识 | `gen_random_uuid()` |
| `JSONB` | 二进制 JSON | 可建 GIN 索引 |
| `CHECK` | 自定义条件 | 违反抛 `CheckViolation` |
| `UNIQUE` | 唯一 | 允许多个 NULL |
| `PRIMARY KEY` | 唯一且非空 | 可复合 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 用 `REAL` 存金额 | 精度丢失 | `NUMERIC` |
| 用 `TIMESTAMP` 存带时区时间 | 时区丢失 | `TIMESTAMPTZ` |
| 以为 `UNIQUE` 不允许 NULL | 多行 NULL 可共存 | 需要加 `NOT NULL` |
| 复合主键写成两个 `PRIMARY KEY` | 语法错误 | 一个表级 `PRIMARY KEY(a,b)` |

## 毕业自查

- [ ] 13/13 通过
- [ ] 能解释 `SERIAL` 为什么不是真实类型
- [ ] 动手题：给 `score` 加 `CHECK (score BETWEEN 0 AND 100)` 并验证
