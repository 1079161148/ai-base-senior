# 07 三范式实战

## 一句话结论

1NF 要求列原子，2NF 消除对复合主键的**部分依赖**，3NF 消除非主键列之间的**传递依赖**。这一章先建反例，再拆到 3NF，最后用 `JOIN` 查回完整信息并演示「冗余导致更新异常」。

## 最小可运行案例

```sql
-- 3NF 反例：dept_name 依赖 dept_id，dept_id 又依赖主键
CREATE TABLE bad_3nf (id SERIAL PRIMARY KEY, name TEXT, dept_id INT, dept_name TEXT);

-- 拆法
CREATE TABLE dept (id INT PRIMARY KEY, name TEXT);
CREATE TABLE student (id SERIAL PRIMARY KEY, name TEXT, dept_id INT REFERENCES dept(id));
SELECT s.name, d.name FROM student s JOIN dept d ON s.dept_id = d.id;
```

## 怎么跑

```powershell
cd "01-能建表\07-三范式实战\examples"
uv run python verify.py
```

## 核心 API 速查

| 范式 | 要求 | 反例 |
| --- | --- | --- |
| 1NF | 列不可再分 | `phones='111,222'` |
| 2NF | 满足 1NF，非主键列完全依赖主键 | `product_name` 只依赖复合主键的一部分 |
| 3NF | 满足 2NF，非主键列互不依赖 | `dept_name` 依赖 `dept_id` |
| `JOIN` | 拆表后查回信息 | 第 12 章详讲 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 一列存多个值 | 无法按单值查询 | 拆子表 |
| 复合主键下列只依赖部分 | 冗余 | 拆表 |
| 传递依赖留在主表 | 更新异常 | 拆成查找表 |
| 为了「性能」一律反范式 | 更新异常 | 先 3NF，再有证据地反范式 |

## 毕业自查

- [ ] 9/9 通过
- [ ] 能各举一个 1NF/2NF/3NF 反例
- [ ] 动手题：给 `good_phone` 加 `UNIQUE(phone)` 会有什么后果
