# 04 CREATE 类型与约束 · 完整版

## 0. 怎么用

先跑 13/13，再读第 4 节理解「约束在数据库层兜底」的意义。

## 1. 概念

表结构 = 列 + 类型 + 约束。约束不是应用层的 `if`，而是数据库最后一道防线。

## 2. 机制

```text
INSERT → 解析 → 默认值填充 → 约束检查 → 写入堆表 → 更新索引
                              ↑
                        违反则整条语句失败
```

## 3. API 逐个拆解

| API | 作用 | 注意 |
| --- | --- | --- |
| `SERIAL` | 自增 | 展开为 `int + sequence + default` |
| `gen_random_uuid()` | 生成 UUID | PG13+ 内置 |
| `JSONB` | 二进制 JSON | 保留类型、支持索引 |
| `information_schema.columns` | 列元数据 | `data_type` 是标准化名称 |
| `psycopg.errors.CheckViolation` | 约束异常 | 捕获它证明约束生效 |

## 4. 边界条件

- `UNIQUE` 允许多个 NULL，因为 NULL 互不相等。
- `SERIAL` 的 sequence 非事务性，回滚后 id 有空洞。
- `NUMERIC(5,2)` 表示总共 5 位、小数 2 位，最大 `999.99`。

## 5. 注意事项对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| REAL 存金额 | 精度误差 | NUMERIC | 原仓库 02 |
| TIMESTAMP 存带时区时间 | 时区丢失 | TIMESTAMPTZ | 原仓库 02 |
| UNIQUE 当 NOT NULL | 多行 NULL | 两个都写 | 实测 |
| 两个 PRIMARY KEY | 语法错误 | 表级复合主键 | 实测 |
| SERIAL 当真实类型 | 元数据看不到 | 查列类型是 integer | 实测 |
| 不设 DEFAULT | 插入必须给值 | 显式默认值 | 原仓库 02 |
| CHECK 写死常量 | 永远真/假 | 引用列 | 实测 |
| 主键用业务字段 | 变更麻烦 | 代理键 + UNIQUE | 原仓库 03 |
| VARCHAR 不写长度 | 语义弱 | 显式长度 | 原仓库 02 |
| JSON 当 JSONB | 无索引、慢 | 用 JSONB | 原仓库 07 |
| gen_random_uuid 未启用 | 函数不存在 | PG13+ 内置 | 实测 |
| 约束命名缺失 | 报错信息不友好 | `CONSTRAINT 名字 CHECK` | 实测 |
| 在建表后加约束 | 需 ALTER | 第 05 章 | 实测 |
| 不查 information_schema | 靠猜类型 | 查元数据 | 实测 |
| 用 `id int` 不加主键 | 可重复 | PRIMARY KEY | 原仓库 02 |
| 捕获宽泛 Exception | 掩盖问题 | 捕获具体异常 | 实测 |
| 事务里回滚后继续用连接 | 状态异常 | 重开或 rollback | 实测 |
| 把 JSONB 当 TEXT 比较 | 语义错误 | 用 `?`/`@>` | 原仓库 07 |

## 6. 最佳实践

约束尽量建在库里；应用层校验负责体验，数据库约束负责底线。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | 原仓库 | 02 DDL 课件 |

> 本次实测 13/13，CHECK 与 UNIQUE 分别抛出 `CheckViolation` 与 `UniqueViolation`。

## 8. 毕业自查

- [ ] 13/13 通过
- [ ] 能说出四种约束

## 9. 下一章

第 05 章学 `ALTER`：如何安全演进表结构。
