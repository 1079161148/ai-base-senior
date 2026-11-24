# 09 SELECT 与 WHERE

## 一句话结论

`SELECT` 决定「看哪些列」，`WHERE` 决定「看哪些行」。条件里 `=`、`IN`、`BETWEEN`、`LIKE`、`IS NULL` 各有边界；尤其 **`NULL = NULL` 不成立**，必须用 `IS NULL`。

## 最小可运行案例

```sql
SELECT name AS 姓名, score 成绩 FROM students
WHERE age >= 20 AND score BETWEEN 80 AND 95;
SELECT * FROM students WHERE email IS NULL;
```

## 怎么跑

```powershell
cd "02-能查数\09-SELECT与WHERE\examples"
uv run python verify.py
```

## 核心 API 速查

| 语法 | 作用 |
| --- | --- |
| `AS` / 空格 | 列别名，`AS` 可省略 |
| `IN (...)` | 多值等值 |
| `BETWEEN a AND b` | 闭区间 |
| `LIKE '张%'` | `%` 任意长度，`_` 单字符 |
| `IS NULL` | 判断空值，不能用 `=` |
| `AND` / `OR` | 逻辑组合 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `WHERE col = NULL` | 永远查不到 | `IS NULL` |
| `BETWEEN` 忘加上界 | 语义错 | 写全 `a AND b` |
| `LIKE '%x'` 全表扫描 | 慢 | 前缀索引或全文检索 |
| 只用 `SELECT *` | 传输多余列 | 显式列名 |

## 毕业自查

- [ ] 16/16 通过
- [ ] 能解释为什么 `NULL = NULL` 返回 NULL
- [ ] 动手题：用 `NOT IN` 替换 `IN`，注意 NULL 陷阱
