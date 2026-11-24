# 05 ALTER 与结构演进

## 一句话结论

`ALTER TABLE` 能加列、删列、改类型、改默认值、加约束、重命名；改类型时若无法隐式转换必须用 `USING` 给出规则。`DROP` 删结构，`TRUNCATE` 只清数据并可 `RESTART IDENTITY`。这一章 12 条断言把每种演进都跑一遍。

## 最小可运行案例

```sql
ALTER TABLE students ALTER COLUMN score TYPE INTEGER USING score::INTEGER;
ALTER TABLE students ADD CONSTRAINT score_check CHECK (score >= 0 AND score <= 100);
ALTER TABLE students RENAME COLUMN score TO total_score;
```

## 怎么跑

```powershell
cd "01-能建表\05-ALTER与结构演进\examples"
uv run python verify.py
```

## 核心 API 速查

| 语句 | 作用 | 注意 |
| --- | --- | --- |
| `ADD COLUMN` | 加列 | 有默认值会重写表（PG11 后优化） |
| `DROP COLUMN` | 删列 | 依赖对象会阻塞 |
| `ALTER COLUMN TYPE ... USING` | 改类型 | 无法隐式转换时必须给 |
| `SET/DROP DEFAULT` | 默认值 | 不影响已有行 |
| `SET NOT NULL` | 非空约束 | 已有 NULL 会失败 |
| `ADD CONSTRAINT` | 加约束 | 已有坏数据会失败 |
| `TRUNCATE ... RESTART IDENTITY` | 清空并重置序列 | DDL，PG 中可回滚 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 改类型不加 `USING` | `cannot be cast automatically` | 给显式转换 |
| 把 `DROP DEFAULT` 当删列 | 默认值消失但列还在 | 用 `DROP COLUMN` |
| `TRUNCATE` 后以为 id 继续 | 默认不重置 | 需 `RESTART IDENTITY` |
| 直接 `DROP TABLE` 被外键阻塞 | 依赖错误 | 先删子表或 `CASCADE` |

## 毕业自查

- [ ] 12/12 通过
- [ ] 能解释 `USING` 什么时候必需
- [ ] 动手题：把 `USING score::INTEGER` 去掉，看报什么错
