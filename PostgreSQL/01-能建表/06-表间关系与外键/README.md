# 06 表间关系与外键

## 一句话结论

1:1 在子表外键上加 `UNIQUE`；1:N 在「多」的一方加外键且**不加** `UNIQUE`；M:N 必须引入中间表，两个外键组成联合主键。外键的 `ON DELETE` 行为决定父行删除时子行怎么办。这一章 10 条断言覆盖三种关系与三种删除行为。

## 最小可运行案例

```sql
CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL REFERENCES users(id),  -- 1:1
    bio TEXT
);
CREATE TABLE enrollments (
    student_id INT REFERENCES students(id),
    course_id INT REFERENCES courses(id),
    PRIMARY KEY (student_id, course_id)                -- M:N
);
```

## 怎么跑

```powershell
cd "01-能建表\06-表间关系与外键\examples"
uv run python verify.py
```

## 核心 API 速查

| 关系 | 实现方式 |
| --- | --- |
| 1:1 | 子表外键 + `UNIQUE` |
| 1:N | 多方外键，不加 `UNIQUE` |
| M:N | 中间表 + 两个外键 + 联合主键 |
| `ON DELETE CASCADE` | 父删子也删 |
| `ON DELETE SET NULL` | 子外键置空 |
| `ON DELETE RESTRICT` | 有子行则禁止删父 |
| `pg_constraint` | 外键元数据，`contype='f'` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 1:1 忘加 `UNIQUE` | 退化成 1:N | 外键加 UNIQUE |
| 1:N 加了 `UNIQUE` | 一个父只能有一个子 | 去掉 UNIQUE |
| M:N 直接互加外键 | 无法表达多对多 | 加中间表 |
| 外键列类型与主键不一致 | 建表报错 | 类型必须完全相同 |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能画出电商库 ERD 的三种关系
- [ ] 动手题：把 `ON DELETE CASCADE` 改成 `RESTRICT`，看哪条断言变红
