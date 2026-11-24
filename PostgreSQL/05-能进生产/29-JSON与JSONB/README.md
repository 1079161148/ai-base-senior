# 29 JSON 与 JSONB

## 一句话结论

`JSON` 保留原始文本，`JSONB` 转成二进制、支持索引但丢失键顺序。半结构化数据优先选 `JSONB`，用 `->`（返回 JSON）、`->>`（返回文本）、`@>`（包含）和 GIN 索引查询。

## 最小可运行案例

```sql
CREATE TABLE events (payload JSONB);
CREATE INDEX idx ON events USING gin(payload);
SELECT * FROM events WHERE payload @> '{"user":"alice"}';
```

## 怎么跑

```powershell
cd "05-能进生产\29-JSON与JSONB\examples"
uv run python verify.py
```

## 核心 API 速查

| 操作符 | 作用 |
| --- | --- |
| `->` | 取 JSON 值 |
| `->>` | 取文本 |
| `#>` | 路径取 JSONB |
| `@>` | 包含 |
| `?` / `?|` / `?&` | 键存在 |
| `jsonb_set` | 修改 |
| `jsonb_agg` | 聚合 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 用 JSON 建索引 | 不支持 | 用 JSONB |
| `->` 当文本用 | 带引号 | 用 `->>` |
| 用 LIKE 查 JSON | 慢且不准 | 用 `@>` |
| 忘建 GIN 索引 | 全表扫 | 建索引 |

## 毕业自查

- [ ] 14/14 通过
- [ ] 能说出 JSON 与 JSONB 的差别
- [ ] 动手题：用 `jsonb_path_query` 重写一个 `@>` 查询
