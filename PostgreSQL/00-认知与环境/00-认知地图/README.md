# 00 认知地图

## 一句话结论

先别急着写 SQL。这一章只回答三件事：**PostgreSQL 是什么、凭什么选它、怎么证明环境真的可用**。验收脚本连真库跑 9 条断言，全绿才算环境合格。

## 最小可运行案例

```python
from common import Checker

c = Checker(0)
print(c.scalar("SELECT version()"))       # PostgreSQL 16.15 ...
print(c.scalar("SELECT current_database()"))  # study
raise SystemExit(c.finish())
```

`Checker(0)` 会建一个名为 `ch00` 的独立 schema，所有对象都落在里面，不污染其他章节。

## 怎么跑

```powershell
cd E:\ai-agent-study\PostgreSQL
uv sync
cd "00-认知与环境\00-认知地图\examples"
uv run python verify.py
```

预期：`结果：9/9 通过`。若报连接失败，先跑 `docker ps --filter name=pg16-study`。

## 核心 API 速查

| 对象 | 作用 | 参数 / 默认 |
| --- | --- | --- |
| `Checker(n)` | 建 `chNN` schema 并连接 | `n` 为章号 |
| `c.scalar(sql)` | 取第一行第一列 | 无结果会断言失败 |
| `c.rows(sql)` | 取全部行（tuple 列表） | — |
| `c.ok(label, cond, detail)` | 打印 PASS/FAIL | `detail` 可省 |
| `c.equal(label, a, b)` | 断言相等 | 打印实际与期望 |
| `psql \l` | 列出数据库 | — |
| `psql \conninfo` | 查看当前连接 | — |
| `psql \q` | 退出 | — |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 把 PostgreSQL 当 MySQL 用 | `SERIAL`、`RETURNING`、`ON CONFLICT` 都不会用 | 按 PostgreSQL 特性学 |
| 直接在公共 schema 建表 | 章节互相污染 | 每章用独立 schema |
| 用 5432 连容器 | 连不上（本教程映射到 54321） | `port=54321` |
| 以为 `pgvector` 已装 | `CREATE EXTENSION` 报错 | 第 36 章才安装 |

## 毕业自查

- [ ] 能说出关系型、文档型、键值型、图数据库各一个代表
- [ ] 能解释为什么把向量放在第 36 章而不是第 1 章
- [ ] 能跑通 9/9 验收
- [ ] 能说出 `ch00` schema 的作用
- [ ] 动手题：把 `Checker(0)` 改成 `Checker(99)`，确认 schema 变成 `ch99`
