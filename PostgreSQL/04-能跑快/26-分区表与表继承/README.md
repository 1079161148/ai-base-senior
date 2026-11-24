# 26 分区表与表继承

## 一句话结论

声明式分区把一张逻辑大表拆成多个物理子表。查询带上分区键时，优化器只扫相关分区（**分区剪枝**）；条件不含分区键时会扫全部。相比表继承，声明式分区支持索引传播和 `ATTACH/DETACH`，更适合生产。

## 最小可运行案例

```sql
CREATE TABLE logs (id bigserial, created date NOT NULL, msg text)
  PARTITION BY RANGE (created);
CREATE TABLE logs_2025 PARTITION OF logs
  FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
```

## 怎么跑

```powershell
cd "04-能跑快\26-分区表与表继承\examples"
uv run python verify.py
```

## 核心 API 速查

| 语法 | 作用 |
| --- | --- |
| `PARTITION BY RANGE` | 范围分区 |
| `PARTITION OF ... FOR VALUES` | 定义分区 |
| `DEFAULT` | 兜底分区 |
| `DETACH PARTITION` | 卸载分区 |
| `ATTACH PARTITION` | 挂载分区 |
| `pg_inherits` | 分区关系 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 分区键不在查询条件 | 扫所有分区 | 带上分区键 |
| 无 DEFAULT 分区 | 越界插入报错 | 建兜底分区 |
| 分区键加函数 | 剪枝失效 | 直接比较 |
| 表继承当分区用 | 无索引传播 | 用声明式分区 |

## 毕业自查

- [ ] 11/11 通过
- [ ] 能在 EXPLAIN 里看出剪枝
- [ ] 动手题：删掉 DEFAULT 分区，插入越界数据看报错
