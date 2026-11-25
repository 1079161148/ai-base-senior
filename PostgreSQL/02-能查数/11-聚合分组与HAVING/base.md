# 11 聚合、分组与 HAVING · 完整版

## 0. 怎么用

跑 11/11，再看第 4 节理解分组时序。

## 1. 概念

聚合是把多行折叠成一行。分组是「先分类，再折叠」。

## 2. 机制

```text
FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT
```

## 3. API 逐个拆解

| API | 作用 | 注意 |
| --- | --- | --- |
| `COUNT(*)` | 数行 | 计入 NULL 行 |
| `COUNT(col)` | 数非空值 | 漏 NULL |
| `AVG/SUM` | 数值聚合 | 忽略 NULL |
| `GROUP BY` | 分组键 | SELECT 非聚合列必须在其中 |
| `HAVING` | 组过滤 | 可用聚合函数 |

## 4. 边界条件

- 空表上 `COUNT` 返回 0，其他聚合返回 NULL。
- `HAVING` 不配 GROUP BY 时把整表当成一组。
- 多列 GROUP BY 按组合分组。

## 5. 注意事项对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| WHERE 用聚合 | 报错 | HAVING | 实测 |
| 非聚合列不在 GROUP BY | 报错 | 补进去 | 实测 |
| COUNT(col) 数行 | 漏 NULL | COUNT(*) | 实测 |
| AVG 含 NULL | 被忽略 | COALESCE | 实测 |
| HAVING 不用 GROUP BY | 整表一组 | 显式分组 | 实测 |
| 分组后不排序 | 顺序不定 | ORDER BY | 第 10 章 |
| 分组键含 NULL | 单独成组 | 可过滤 | 实测 |
| SUM 溢出 | 数值越界 | 用 BIGINT/NUMERIC | 实测 |
| 聚合字符串 | 报错 | string_agg | 通用实践 |
| 不测空结果 | 边界漏 | HAVING 不可能条件 | 实测 |
| 用 DISTINCT 代替 GROUP BY | 无法聚合 | 两者配合 | 实测 |
| 分组大表无索引 | 慢 | 第 22 章 | 通用实践 |
| 别名用于 HAVING | PG 不允许 | 重复表达式 | 实测 |
| 多列分组漏一列 | 组粒度错 | 检查业务键 | 实测 |
| 聚合结果不取整 | 展示冗长 | ROUND | 实测 |
| 把 HAVING 当 WHERE | 性能差 | 能前置就前置 | 实测 |
| 不查执行计划 | 分组慢不知原因 | EXPLAIN | 通用实践 |
| 跳过验收 | 分组错不自知 | 11/11 再走 | 实测 |

## 6. 最佳实践

过滤尽量放 WHERE，只有依赖聚合结果的才放 HAVING。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | 官方文档 | PostgreSQL 16 官方手册 |

> 本次实测 11/11，`COUNT(price)=8`、`COUNT(*)=9`（含 1 行 NULL）。

## 8. 毕业自查

- [ ] 12/12 通过
- [ ] 能解释 WHERE 与 HAVING 的区别

## 9. 下一章

第 12 章学四种 JOIN。
