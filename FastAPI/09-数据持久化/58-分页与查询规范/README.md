# 58 分页与查询规范

## 一句话结论

`LIMIT/OFFSET` 的成本是 **O(offset)**：翻到第 4950 页要先扫 99000 行。实测 10 万行下，首页 `OFFSET 0` 为 **0.055ms**，`OFFSET 99000` 为 **7.294ms（133 倍）**；换成游标（keyset）分页后，深页 `0.058ms`，与首页同量级。代价是游标**不能跳页**、**只能按游标字段顺序翻**。索引是否生效可以用 `EXPLAIN QUERY PLAN` 硬断言：实测有索引是 `SCAN events USING INDEX idx_events_created`（无临时排序），按无索引列排序则是 `SCAN events` + `USE TEMP B-TREE FOR ORDER BY`。

## 最小可运行案例

```python
# 偏移分页：能跳页，深页慢
SELECT id, created_at, title, level
FROM events
ORDER BY created_at DESC, id DESC
LIMIT ? OFFSET ?;

# 游标分页：深页恒定，只能顺序翻
SELECT id, created_at, title, level
FROM events
WHERE (created_at, id) < (?, ?)
ORDER BY created_at DESC, id DESC
LIMIT ?;
```

配套索引（**排序方向要写进索引**）：

```sql
CREATE INDEX idx_events_created ON events (created_at DESC, id DESC);
```

```python
def encode_cursor(created_at: str, event_id: int) -> str:
    return f"{created_at}|{event_id}"   # 生产应 base64 + 签名


@app.get("/events/cursor")
def list_by_cursor(conn: DbDep, limit: int = Query(20, ge=1, le=100), cursor: str | None = None):
    rows = conn.execute(KEYSET_FIRST_SQL, (limit + 1,)).fetchall() if cursor is None else ...
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = encode_cursor(page[-1]["created_at"], page[-1]["id"]) if has_more else None
    return {"items": page, "next_cursor": next_cursor, "has_more": has_more}
```

## 怎么跑

```powershell
cd "09-数据持久化\58-分页与查询规范\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 数据与索引 -> 100000 行，索引 ['idx_events_created']
[PASS] 偏移首页 -> 100000,99999,99998
[PASS] 偏移深页 -> 3,2,1
[PASS] 游标首页一致 -> 两页完全相同
[PASS] 游标翻页无缝 -> 15 条连续：100000…99986
[PASS] 游标最后一页 -> 空页，next_cursor=None
[PASS] limit 边界 -> 0/101 → 422，100 → 200
[PASS] offset 负数 -> 422
[PASS] 非法游标 -> 400 游标格式错误
[PASS] 索引执行计划 -> SCAN events USING INDEX idx_events_created
[PASS] 无索引执行计划 -> SCAN events | USE TEMP B-TREE FOR ORDER BY
[PASS] 深页偏移变慢 -> 首页 0.055ms → 深页 7.294ms（133×）
[PASS] 游标耗时恒定 -> 首页 0.038ms → 深页 0.058ms
[PASS] COUNT 代价 -> 4.673ms

结果：14/14 通过
```

## 核心 API 速查

| 方案 | SQL | 成本 | 能跳页 |
| --- | --- | --- | --- |
| 偏移 | `LIMIT ? OFFSET ?` | O(offset) | 是 |
| 游标 | `WHERE (a,b) < (?,?)` | O(limit) | 否 |

| 需求 | 写法 |
| --- | --- |
| 跳页 / 显示总页数 | 偏移 + `COUNT(*)` |
| 无限滚动 / 深页 | 游标 |
| 判断还有没有下一页 | 多取 1 条（省 `COUNT(*)`）|
| 验证索引 | `EXPLAIN QUERY PLAN <sql>` |

| 实测 | 值 |
| --- | --- |
| 10 万行首页 offset | 0.055ms |
| 10 万行深页 offset（99000）| 7.294ms |
| 游标深页 | 0.058ms |
| `COUNT(*)` | 4.673ms |
| 有索引排序计划 | `SCAN events USING INDEX idx_events_created` |
| 无索引排序计划 | `SCAN events` + `USE TEMP B-TREE FOR ORDER BY` |
| `limit=0/101` | 422 |
| 非法游标 | 400 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 深页用 `OFFSET` | 第 1000 页 7ms，第 10 万页 70ms | 游标 |
| 游标只放 `created_at` | 同时间戳的记录被跳过/重复 | 带上唯一键 `(created_at, id)` |
| 索引方向与 `ORDER BY` 相反 | 用不上索引，走临时 B 树 | 索引方向写成 `DESC` |
| 索引只有 `created_at` | 仍需回表 + 部分排序 | 复合索引 `(created_at, id)` |
| 每页都 `COUNT(*)` | 每次全表扫 4.6ms | 缓存总数 / 多取 1 条 |
| `WHERE date(created_at) = ?` | 函数包裹列，索引失效 | 存范围查询 |
| `LIKE '%关键词%'` | 全表扫 | 全文索引 / 前缀匹配 |
| `ORDER BY` 与 `WHERE` 字段不匹配索引 | 残留 `TEMP B-TREE` | 按查询建复合索引 |
| 游标明文暴露主键 | 可枚举/越权 | base64 + 签名 + 权限校验 |
| 游标不带方向 | 反向翻页结果错 | 游标里带排序方向 |
| `limit` 不设上限 | 一次拉 10 万条 | `le=100` |
| `offset` 允许负数 | 数据库行为不一致 | `ge=0` |
| 非法游标直接 500 | 客户端拿到堆栈 | 捕获后 400 |
| 分页接口返回 `total` 但用游标 | 又要 `COUNT(*)` | 二选一，别混 |
| 用 `OFFSET` 做无限滚动 | 新数据插入导致重复/漏行 | 游标 |
| 只测首页 | 深页问题漏测 | 测 `offset=TOTAL-3` |
| 不写 `EXPLAIN` 就以为走了索引 | 实际全表扫 | 断言执行计划 |
| 10 万行循环 `commit()` 造数据 | 灌数据要几分钟 | `executemany` + 单事务 |

## 毕业自查

- [ ] 能解释 `OFFSET 99000` 为什么要扫 99000 行
- [ ] 能写出 keyset SQL 与配套复合索引
- [ ] 能解释游标为什么要带唯一键
- [ ] 能用 `EXPLAIN QUERY PLAN` 判断索引是否生效
- [ ] 能说清 offset 与 cursor 的取舍
- [ ] 动手题一：把 `/events` 改成游标版并保持响应结构兼容
- [ ] 动手题二：给 `title` 加前缀索引，对比 `LIKE '事件 0001%'` 的计划

> 想看分页背后的 B 树扫描、行值比较的索引匹配条件、`COUNT(*)` 的替代方案、游标签名的具体做法、18 条坑，继续读 [`base.md`](./base.md)。