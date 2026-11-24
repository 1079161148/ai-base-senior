# 08 INSERT 与 UPSERT · 完整版

## 0. 怎么用

先跑 9/9，再看第 2 节理解冲突仲裁。

## 1. 概念

UPSERT = INSERT 遇到唯一约束冲突时改走 UPDATE，避免「先查再插」的竞态。

## 2. 机制

```text
INSERT → 检查唯一索引 → 冲突 → DO UPDATE/NOTHING → RETURNING
```

## 3. API 逐个拆解

| API | 作用 | 注意 |
| --- | --- | --- |
| `VALUES` | 提供新行 | 多组用逗号分隔 |
| `INSERT ... SELECT` | 迁移数据 | WHERE 可过滤 |
| `RETURNING` | 返回受影响行 | PG 特性 |
| `ON CONFLICT` | 冲突目标 | 需唯一约束 |
| `EXCLUDED` | 新行别名 | 旧行用表名 |

## 4. 边界条件

- `DO NOTHING` 不报错也不更新。
- `RETURNING` 在 `DO NOTHING` 时不返回被跳过的行。
- 省略列若有 DEFAULT 用默认值，否则 NULL。

## 5. 注意事项对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 省略列名 | 顺序敏感 | 写列清单 | 原仓库 04 |
| 无唯一约束 UPSERT | 报错 | 加 UNIQUE | 实测 |
| `VALUES(name)` 引用新值 | 语义错 | EXCLUDED.name | 实测 |
| DO NOTHING 后 RETURNING | 无行返回 | 用 DO UPDATE | 实测 |
| 多行插入不按顺序 | id 分配乱 | 用 ORDER BY 查 | 实测 |
| INSERT SELECT 无 WHERE | 全表搬 | 加过滤 | 原仓库 04 |
| 忘了 NOT NULL 列 | 插入失败 | 补值或默认值 | 原仓库 02 |
| 金额用 REAL | 精度丢失 | NUMERIC | 原仓库 02 |
| 不测冲突分支 | 上线才炸 | 双次插入 | 实测 |
| 用 `REPLACE INTO` | PG 不支持 | ON CONFLICT | 实测 |
| 并发 UPSERT 无事务 | 部分成功 | 包事务 | 第 17 章 |
| RETURNING 大表 | 传输量大 | 只取需要的列 | 实测 |
| 不命名唯一约束 | 报错难懂 | 显式命名 | 实测 |
| 把 EXCLUDED 当表名 | 语义混淆 | 它是伪表 | 实测 |
| 批量插入无分批 | 锁时间长 | 分批提交 | 实测 |
| 用 SERIAL 当前值 | 并发错 | RETURNING id | 实测 |
| 忽略默认值 | 数据不完整 | 显式利用默认值 | 原仓库 04 |
| 跳过验收 | 冲突逻辑未验证 | 9/9 再走 | 实测 |

## 6. 最佳实践

所有「存在则更新」场景用 UPSERT，不要先 SELECT 再 INSERT。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | 原仓库 | 04 DML 课件 |

> 本次实测 9/9，DO UPDATE 后 age=99，DO NOTHING 后仍为 99。

## 8. 毕业自查

- [ ] 8/8 通过
- [ ] 能写带 RETURNING 的 UPSERT

## 9. 下一章

第 09 章系统学 SELECT 与 WHERE。
