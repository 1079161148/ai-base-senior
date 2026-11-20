# 57 事务边界

## 一句话结论

事务放 `yield` 依赖：`yield` 正常返回 → `commit`，抛任何异常 → `rollback`，`finally` → `close`。实测批量写 `[ok1, ok2, dup]` 返回 409 且 **`ok1/ok2` 都没落库**；`HTTPException(418)` 和未捕获的 `RuntimeError`（500）同样回滚；两个 `yield` 依赖的清理是**后进先出**（`marker:close` 在 `db:close` 之前）；同一请求里 `get_db` 只执行 **1 次**（依赖缓存），所以多个仓储共享同一事务。

## 最小可运行案例

```python
import sqlite3
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException


def get_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect("app.db", check_same_thread=False)
    try:
        yield conn
        conn.commit()          # 只有正常返回才提交
    except Exception:
        conn.rollback()        # 任何异常都回滚
        raise
    finally:
        conn.close()


app = FastAPI()


@app.post("/items/batch")
def create_batch(names: list[str], conn=Depends(get_db)) -> dict[str, int]:
    for name in names:
        conn.execute("INSERT INTO items (name) VALUES (?)", (name,))
    # 中途抛异常 → 前面写的全部回滚
    return {"created": len(names)}
```

## 怎么跑

```powershell
cd "09-数据持久化\57-事务边界\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 成功提交 -> begin → commit → close
[PASS] 批量全成功 -> b,c
[PASS] 批量原子回滚 -> 409，d 被回滚，剩余 ['a']
[PASS] 失败走 rollback -> begin → rollback → close
[PASS] 未捕获异常回滚 -> 500，vanish 未落库
[PASS] HTTPException 回滚 -> 418，cup 未落库
[PASS] 领域异常 handler -> 409 来自 exception_handler
[PASS] 审计同事务 -> 2 条审计
[PASS] 审计随事务回滚 -> 审计只剩成功那条
[PASS] 仓储无 commit -> 无 commit / rollback
[PASS] get_db 三要素 -> commit / rollback / close
[PASS] 连接间隔离 -> 提交前 0，提交后 1
[PASS] yield 清理顺序 -> db:begin → marker:begin → marker:end → marker:close → db:commit → db:close
[PASS] 依赖缓存单连接 -> db:begin 出现 1 次

结果：14/14 通过
```

## 核心 API 速查

| 位置 | 职责 | 实测 |
| --- | --- | --- |
| `get_db` | begin/commit/rollback/close | 三要素齐全 |
| `repository` | 只 `execute` | 无 `commit` |
| `service` | 业务规则 + 原子语义 | 循环写 |
| `router` | HTTP 语义 | 不写事务 |
| `exception_handler` | 领域异常 → 状态码 | 生效 |

| 场景 | 状态码 | 数据 |
| --- | --- | --- |
| 全部成功 | 201 | 全部落库 |
| 中途重名 | 409 | **全部回滚** |
| `RuntimeError` | 500 | 全部回滚 |
| `HTTPException(418)` | 418 | 全部回滚 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 仓储里 `commit()` | 事务边界碎，批量写不原子 | 上移到依赖 |
| 只在 `try` 里 commit，不 rollback | 异常后连接带脏事务 | `except: rollback; raise` |
| 忘了 `finally: close` | 连接泄漏 | 显式关闭 |
| 用 `with sqlite3.connect()` 当关闭 | 不关闭（第 56 章实测）| `try/finally` |
| 在 service 里开事务 | 跨仓储无法原子 | 依赖层统一 |
| 用 `HTTPException` 表达业务规则 | 事务与 HTTP 耦合 | 领域异常 + handler |
| 以为 4xx 不回滚 | 数据脏写 | 4xx 也抛异常，也回滚 |
| 手动 `savepoint` 过度 | 复杂难维护 | 一请求一事务 |
| 事务里做外部 HTTP 调用 | 长事务锁库 | 拆开/异步补偿 |
| 依赖里 `commit` 后还写 | 第二次写不在事务里 | 只在末尾 commit |
| 依赖顺序搞混 | 清理顺序反了 | 记住后进先出 |
| 多个 `get_db` 依赖 | 以为开了多个事务 | 缓存复用同一连接 |
| 用 `autocommit` 又手写事务 | 全部即时提交 | 二选一 |
| 长事务里 `SELECT` 全表 | 锁住写 | 缩短事务 |

## 毕业自查

- [ ] 能写出完整的三段式 `get_db`
- [ ] 能解释为什么仓储不能 `commit`
- [ ] 能证明批量写中途失败会全回滚
- [ ] 知道 `HTTPException` 也回滚
- [ ] 知道 `yield` 依赖清理是后进先出
- [ ] 动手题一：加 `POST /items/batch` 的 `savepoint` 版本对比复杂度
- [ ] 动手题二：把 `get_db` 换成 SQLAlchemy `session` 版本

> 想看 `yield` 依赖的收尾时机（响应前/后）、`commit` 失败为什么改不了状态码、嵌套事务与 `savepoint`、长事务的锁代价、18 条坑，继续读 [`base.md`](./base.md)。