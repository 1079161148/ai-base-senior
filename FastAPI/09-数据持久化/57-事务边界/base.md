# 57 事务边界 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「`yield` 依赖的收尾到底在什么时候、异常怎么传播、为什么 4xx 也要回滚、什么不该放在事务里」拆开。学完这章，你能判断一个「写了一半」的 bug 是事务边界错了还是异常被吞了。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 55 章（生命周期）、第 56 章（分层） |
| 覆盖范围 | `yield` 依赖事务、commit/rollback 时机、原子性、异常传播 |
| 明确不覆盖 | 分布式事务、Saga、savepoint 嵌套、隔离级别详解 |
| 学完验收 | 能跑通 `verify.py` 14/14、能解释三种失败都回滚 |

## 0. 怎么用这份文件

**依据约定**：`` `[Xn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 事务归属
2 机制（第 2 节）    → yield 的三段
3 API（第 3 节）     → 依赖链
4 边界（第 4 节）    → 原子性/异常/顺序
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 不该放事务里的
```

## 1. 概念：一次请求一个事务

| 层级 | 事务边界 | 后果 |
| --- | --- | --- |
| 每条语句 | autocommit | 无法原子 |
| 每个仓储方法 | 方法级 | 跨方法无法原子 |
| **每个请求** | `yield` 依赖 | 一次业务操作原子 ✓ |
| 每个后台任务 | 手动 | 需显式管理 |

业务操作天生是「请求级」的，所以边界放请求级。

## 2. 机制：`yield` 依赖的三段

```python
def get_db():
    conn = connect()        # ① 请求前
    try:
        yield conn          # ② 交给端点
        conn.commit()       # ③ 正常返回
    except Exception:
        conn.rollback()     # ③ 异常
        raise
    finally:
        conn.close()        # ④ 无论如何
```

实测事件序列：

| 场景 | 序列 |
| --- | --- |
| 成功 | `db:begin → db:commit → db:close` |
| 失败 | `db:begin → db:rollback → db:close` |

### 2.1 清理顺序（实测）

两个 `yield` 依赖：

```text
db:begin → marker:begin → marker:end → marker:close → db:commit → db:close
```

`marker` 后进先出，先清理；`db` 最后提交并关闭。

### 2.2 依赖缓存（实测）

同一请求里 `db:begin` 只出现 **1 次**，说明 `get_db` 被缓存复用——所以「主表仓储」和「审计仓储」拿到的是同一个连接、同一个事务。

## 3. API 逐个拆解

| 依赖 | 类型 | 作用 |
| --- | --- | --- |
| `get_db` | `yield` | 事务边界 |
| `get_repository` | 普通 | 组装仓储 |
| `get_service` | 普通 | 组装服务 |

**只有 `get_db` 是 `yield`**：事务边界必须唯一，多个 `yield` 事务会互相覆盖。

## 4. 边界条件

### 4.1 批量原子性（实测）

```text
POST /items/batch  [{"name":"d"}, {"name":"a"}]   # a 已存在
→ 409 {"detail": "名称已存在：a"}
→ GET /items 仍只有 ["a"]，d 没落库
```

即使 `d` 的 INSERT 已经执行、`create:d` 审计已写入，全部回滚。

### 4.2 三种失败都回滚（实测）

| 抛出 | 状态码 | 数据 |
| --- | --- | --- |
| `DuplicateItemError`（handler 转 409）| 409 | 回滚 |
| `HTTPException(418)` | 418 | 回滚 |
| `RuntimeError`（无 handler）| 500 | 回滚 |

**关键**：`HTTPException` 也是异常，`except Exception` 能捕获，所以 4xx 也会回滚——这是期望行为（业务拒绝就不该留半条数据）。

### 4.3 未提交的数据跨连接可见吗（实测）

```text
writer: INSERT ...             → reader 查: 0
writer: commit                 → reader 查: 1（需先结束读事务）
```

`reader` 的第一次 `SELECT` 会开读事务，保持快照；`commit` 后要 `rollback()` 或重新开始事务才能看到新数据。

### 4.4 `commit` 在响应之后

FastAPI 里 `yield` 依赖的收尾在**响应发送之后**执行。含义：

| 情况 | 结果 |
| --- | --- |
| 端点返回 200，commit 成功 | 正常 |
| 端点返回 200，commit 失败 | 客户端已收到 200，数据没落库（只能记日志告警）|

所以**不要把所有校验都推迟到 commit**：能在 service 层判的先判，让失败发生在响应之前。

> 这一条基于 FastAPI 文档描述的行为，**本次未构造延迟约束实测**。

### 4.5 长事务

事务里做 HTTP 调用 / 发消息 / 等用户输入，会长时间持锁：

| 操作 | 代价 |
| --- | --- |
| 事务内调外部 API | 锁住行/表，其他请求排队 |
| 事务内发邮件 | 同上 |
| 事务内 `sleep` | 同上 |

拆法：事务只包数据库写，外部调用放事务外（或用 outbox 模式，未实现）。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 仓储里 `commit()` | 批量写不原子 | 上移依赖 | 实测 |
| 只 commit 不 rollback | 脏事务残留 | `except: rollback; raise` | 实测 |
| 忘记 `finally: close` | 连接泄漏 | 显式关闭 | `[X1]` |
| `with sqlite3.connect()` 当关闭 | 不关闭（WinError 32）| `try/finally` | 第 56 章 |
| service 里开事务 | 跨仓储不原子 | 依赖层 | `[X2]` |
| 用 `HTTPException` 表达规则 | 层耦合 | 领域异常 | 实测 |
| 以为 4xx 不回滚 | 脏数据 | 会回滚（实测）| 实测 |
| 手动 savepoint | 复杂 | 一请求一事务 | `[X2]` |
| 事务里调外部 API | 长事务锁库 | 移出事务 | `[X3]` |
| commit 后再写 | 不在事务内 | 只在末尾 commit | 实测 |
| 依赖顺序搞反 | 清理顺序错 | 后进先出 | 实测 |
| 多个 `get_db` 参数 | 看似多事务 | 缓存复用 | 实测 |
| autocommit + 手写事务 | 即时提交 | 二选一 | `[X1]` |
| 长事务里全表扫描 | 锁写 | 缩短事务 | `[X3]` |
| 后台任务复用请求连接 | 连接已关 | 新开连接 | `[X1]` |
| 异常被 `except` 吞掉 | 不回滚 | `raise` 继续抛 | 实测 |
| 事务里 `print` 大量日志 | 拖慢 | 结构化 + 异步 | 第 52 章 |
| 只在开发测成功路径 | 回滚没验证 | 三种失败都测 | 第 71 章 |
| 事务里先 commit 再继续写 | 前面已提交，无法整体回滚 | 只在末尾 commit | 实测 |

## 6. 最佳实践与编码建议

### 6.1 分层职责

```text
db.py         → get_db（唯一事务边界）
repository.py → 只 execute，不 commit
service.py    → 业务规则，失败抛领域异常
router.py     → HTTP 语义，不碰事务
main.py       → exception_handler 统一翻译
```

### 6.2 该放事务里 / 外

| 放里面 | 放外面 |
| --- | --- |
| 所有数据库写 | 外部 HTTP 调用 |
| 需要一致性的读 | 发消息/邮件 |
| 审计日志（同库）| 文件/对象存储 |

### 6.3 测试要点

```python
# 【要点】三种失败都要测
client.post("/items/batch", json=[ok, dup])        # 409 + 回滚
client.post("/items/crash", json=...)              # 500 + 回滚
client.post("/items/teapot", json=...)             # 418 + 回滚
```

断言方式：**看数据库**，不要只看状态码。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[X1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/dependencies/dependencies-with-yield/ | `yield` 依赖 |
| `[X2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/sql-databases/ | 会话与事务 |
| `[X3]` | 文档 | https://www.sqlite.org/lang_transaction.html | 事务与锁 |

> **核对状态**：`[X1]`–`[X3]` 为官方文档/规范链接，**本次未逐页直连复核**；成功/失败事件序列、批量原子回滚、rollback 路径、500 与 418 回滚、handler 翻译、审计同事务与回滚、仓储无 commit、提交前后跨连接可见性、清理顺序、依赖缓存均为本机实测，`examples/verify.py` 复现 14/14 通过。`commit` 失败改不了状态码、savepoint、分布式事务**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 事务为什么放请求级
- [ ] `yield` 三段各做什么
- [ ] 为什么 4xx 也回滚
- [ ] 清理顺序为什么是后进先出
- [ ] `commit` 在响应之后的后果

**能写出（代码层）**：

- [ ] 三段式 `get_db`
- [ ] 仓储不 commit
- [ ] 批量原子写
- [ ] 领域异常 handler
- [ ] 回滚测试

**能判断（避坑层）**：

- [ ] 看到仓储 `commit` → 指出边界错
- [ ] 看到只 commit 不 rollback → 指出脏事务
- [ ] 看到 `except` 吞异常 → 指出不回滚
- [ ] 看到事务里调外部 API → 指出长事务
- [ ] 看到多个 `yield` 事务依赖 → 指出重复边界

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] 手工构造 batch 冲突，查库确认回滚
- [ ] 停服务确认无残留 DB 文件

## 9. 下一章衔接

第 58 章 `分页与查询规范`：偏移分页 vs 游标分页、`LIMIT/OFFSET` 的深页性能、`COUNT(*)` 的代价、索引与 `EXPLAIN QUERY PLAN`，讲「百万行为什么不卡」与「什么时候该换游标」。

本章留下的伏笔：

1. 事务边界（57）→ 58 的分页查询也在同一事务里。
2. 仓储只做 SQL（56）→ 58 把分页查询放进仓储。
3. `Query` 参数校验（57 的 `limit`）→ 58 的分页参数约束。