# 40 yield 依赖

## 一句话结论

用生成器写依赖：`yield` 前是准备、`yield` 的值注入端点、`yield` 之后是清理（写在 `finally` 里保证执行）。实测：正常路径 `open → commit → close`，异常路径 `open → rollback → close`；嵌套时**后创建的先清理**（LIFO）；路由抛的 `HTTPException` 会被 `athrow` 进生成器，`except` 能捕获；清理阶段再抛异常**改不了状态码**（响应已发出）。

学完这一章，你能：用 `yield` 管理数据库会话、临时文件、锁，知道异常怎么回滚、清理什么时候执行。

## 最小可运行案例

```python
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

app = FastAPI()


class Session:
    def __init__(self) -> None:
        self.closed = False

    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None:
        self.closed = True


def get_session() -> Iterator[Session]:
    session = Session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    else:
        session.commit()
    finally:
        session.close()


@app.get("/items")
def items(session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    return {"closed_inside": session.closed}
```

完整版本（嵌套 LIFO、async 生成器、依赖捕获异常、反例）见 `examples/main.py`。

## 怎么跑

```powershell
cd "06-依赖注入\40-yield依赖\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 正常生命周期 -> LOG=['open', 'commit', 'close']
[PASS] 响应后清理 -> 响应返回时清理已完成
[PASS] 异常回滚 -> LOG=['open', 'rollback', 'close']
[PASS] 嵌套 LIFO -> LOG=['outer-open', 'inner-open', 'inner-close', 'outer-close']
[PASS] async 生成器 -> LOG=['async-open', 'async-close']
[PASS] 依赖捕获异常 -> 路由异常被依赖感知（LOG=['guarded-error', 'guarded-close']）
[PASS] 无异常路径 -> error=False
[PASS] yield 值注入 -> yield 值 = outer:inner
[PASS] 清理异常不改状态 -> 响应 200 已发出，清理异常不影响状态码
[PASS] 普通函数依赖 -> 普通函数依赖照常工作（但没有清理语义）
[PASS] 校验失败也清理 -> 校验失败/正常路径都会清理（此处正常）
[PASS] async 清理完成 -> async 清理完成

结果：12/12 通过
```

## 核心 API 速查

| 写法 | 说明 |
| --- | --- |
| `def dep() -> Iterator[T]: yield x` | 同步生成器依赖 |
| `async def dep() -> AsyncIterator[T]: yield x` | 异步生成器依赖 |
| `try/finally` | **必须**，保证清理 |
| `except Exception: rollback; raise` | 异常回滚 |
| `else: commit` | 无异常才提交 |

| 实测行为 | 结果 |
| --- | --- |
| 正常路径 | `open → commit → close` |
| 异常路径（`HTTPException`）| `open → rollback → close`，状态码 409 |
| 嵌套依赖清理顺序 | inner-close → outer-close（LIFO）|
| 依赖 `except` 捕获路由异常 | 能（LOG 有 `guarded-error`）|
| 清理阶段抛异常 | 状态码不变（200 已发出）|
| 普通函数依赖 | 正常返回，但**没有清理语义** |
| 端点内访问资源 | `closed=False`（还没清理）|

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 忘了 `finally` | 异常时资源泄漏 | 一律包 `finally` |
| 在 `yield` 后 `return` | 生成器结束，清理不执行 | 用 `finally` |
| 清理阶段抛异常 | 状态码改不了，连接可能断 | 清理里吞并记日志 |
| 在依赖里 `except Exception: pass` | 掩盖错误 | `raise` 重新抛出 |
| 端点内 `await` 之后用已关闭资源 | 取决于实现 | 只在请求内用 |
| 依赖里 `commit` 后 `yield` | 事务过早提交 | `yield` 后提交 |
| 用普通函数写「清理」 | 清理不执行 | 用生成器 |
| 在 `finally` 里做重 IO/网络 | 拖住响应 | 轻量清理 |
| `async` 依赖忘了 `AsyncIterator` | 类型提示不符 | 用 `AsyncIterator` |
| 依赖里自己 `close` 又 `finally` 再关 | 重复关闭 | 幂等关闭 |
| 用 `yield` 依赖做后台任务 | 请求后资源已关 | 第 50 章 |

## 毕业自查

- [ ] 能写出「创建 → yield → finally 清理」的会话依赖
- [ ] 能说出正常/异常路径的执行序列
- [ ] 能解释 LIFO 清理顺序
- [ ] 能说明依赖里 `except` 为什么能捕获路由异常
- [ ] 能解释清理阶段抛异常为什么改不了状态码
- [ ] 动手题一：写一个临时文件依赖（写入 + 删除）
- [ ] 动手题二：写一个「可重试事务」依赖（失败重试 1 次）

> 想看 `AsyncExitStack` 如何管理生成器、异常 `athrow` 的传播路径、与响应发送的时序、18 条坑，继续读 [`base.md`](./base.md)。