# 34 完整建模评审

## 一句话结论

建模评审就是拿一套清单逐项打分：主键、外键、类型、NOT NULL、CHECK、UNIQUE、范式、索引、命名。本章先给一个全用 TEXT、无主键无外键的反例，再建成规范四表模型，用元数据查询逐项核验。

## 最小可运行案例

```sql
-- 反例：所有字段 TEXT，无主键无外键
CREATE TABLE bad_orders (order_no TEXT, customer_name TEXT, total_price TEXT);

-- 评审清单：查主键覆盖
SELECT table_name FROM information_schema.table_constraints
WHERE table_schema='ch34' AND constraint_type='PRIMARY KEY';
```

## 怎么跑

```powershell
cd "05-能进生产\34-完整建模评审\examples"
uv run python verify.py
```

## 评审清单

| 维度 | 检查项 | 达标标准 |
| --- | --- | --- |
| 主键 | 每表有稳定主键 | `PRIMARY KEY` 存在 |
| 外键 | 引用关系显式声明 | `FOREIGN KEY` 存在 |
| 类型 | 金额 NUMERIC、时间 TIMESTAMPTZ | 不用 TEXT 凑合 |
| 必填 | 核心字段 NOT NULL | `is_nullable='NO'` |
| 取值 | 非法值被 CHECK 拦截 | `CHECK` 存在 |
| 唯一 | 业务键 UNIQUE | `UNIQUE` 存在 |
| 范式 | 无重复组、无传递依赖 | 拆分到三范式 |
| 级联 | 删除行为明确 | `ON DELETE` 显式 |
| 索引 | 高频查询有索引 | 见第 22 章 |
| 命名 | 复数表名、语义字段名 | 一致风格 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 金额用 FLOAT | 精度丢失 | NUMERIC |
| 时间用 TEXT | 无法比较排序 | TIMESTAMPTZ |
| 无主键 | 无法唯一定位行 | SERIAL / IDENTITY |
| 隐式级联 | 删除行为不可控 | 显式 ON DELETE |
| 逗号分隔存多值 | 违反 1NF | 拆明细表 |

## 毕业自查

- [ ] 14/14 通过
- [ ] 能独立对一张业务表做完整评审
- [ ] 动手题：给 `bad_orders` 写一份改造方案
