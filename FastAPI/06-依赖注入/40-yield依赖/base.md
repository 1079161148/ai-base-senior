# 40 yield 依赖 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「生成器依赖的生命周期、异常怎么进到依赖里、清理与响应发送的先后、嵌套顺序」拆开。学完这章，你要能写一个不会泄漏连接的会话依赖。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Starlette 1.10.0（本机实测） |
| 前置 | 第 35–37 章（`Depends`、缓存） |
| 覆盖范围 | 生成器依赖、`try/except/else/finally`、异常穿透、嵌套顺序、async 清理 |
| 明确不覆盖 | 后台任务（第 50 章）、连接池实现、事务隔离级别 |
| 学完验收 | 能跑通 `verify.py` 12/12、能画出「请求 → 清理 → 响应」时序、能避开清理阶段炸掉 |

## 0. 怎么用这份文件

**依据约定**：`` `[Yn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 三段式
2 机制（第 2 节）    → ExitStack 与 athrow
3 API（第 3 节）     → 写法、同步/异步
4 边界（第 4 节）    → 时序、异常、嵌套、失败
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 会话模板
```

## 1. 概念：一个依赖管三段

```python
def get_session() -> Iterator[Session]:
    session = Session()          # 1 准备
    try:
        yield session            # 2 使用（注入端点）
    except Exception:            # 3a 异常路径
        session.rollback()
        raise
    else:                        # 3b 正常路径
        session.commit()
    finally:                     # 3c 一定执行
        session.close()
```

| 段 | 执行时机 | 典型动作 |
| --- | --- | --- |
| 准备 | 请求开始，路由前 | 开连接、建临时文件 |
| 使用 | 端点函数体 | 业务 |
| 清理 | 响应发出后 | commit/rollback/close |

## 2. 机制：`AsyncExitStack` + `athrow`

```text
solve_dependencies
  → 创建生成器
  → next(gen) 拿到 yield 值，注入端点
  → 进入 ExitStack 回调：请求结束时 close()
  → 若端点抛异常：gen.athrow(exc) → 依赖内 except 收到
```

| 事实 | 说明 |
| --- | --- |
| 清理在响应之后 | 实测响应返回时 `close` 已完成（TestClient 同步等待）|
| 异常会 `athrow` 进生成器 | 实测依赖 `except` 捕获到路由的 `HTTPException` |
| 清理异常无法改状态码 | 实测 `/bad-cleanup` 仍 200 |
| 嵌套按 LIFO | 实测 `inner-close` 先于 `outer-close` |
| 同请求缓存 | 与普通依赖一致（第 37 章）|

## 3. API 逐个拆解

### 3.1 同步生成器

```python
def dep() -> Iterator[T]:
    ...
    yield value
```

类型标注用 `Iterator[T]` 或 `Generator[T, None, None]`。

### 3.2 异步生成器

```python
async def dep() -> AsyncIterator[T]:
    ...
    yield value
    await cleanup()
```

实测可用，`await` 在清理阶段正常执行。

### 3.3 异常处理三段

| 结构 | 用途 |
| --- | --- |
| `except Exception: rollback; raise` | 回滚并继续上抛 |
| `else: commit` | 只有成功才提交 |
| `finally: close` | 一定释放 |

### 3.4 不要 `return`

生成器里 `return` 会终止迭代，跳过 `finally` 之外的收尾代码。**用 `finally`**。

## 4. 边界条件

### 4.1 时序（实测）

| 阶段 | 状态 |
| --- | --- |
| 端点执行中 | `closed=False` |
| 响应返回给客户端时（TestClient）| `closed=True` |
| 失败请求 | `rollback` 先于 `close` |

### 4.2 异常穿透（实测）

`/session/crash` 抛 `HTTPException(409)`：`LOG == ["open","rollback","close"]`，异常继续上抛变成 409 响应。

### 4.3 依赖内捕获异常

`/guarded` → `LOG == ["guarded-error","guarded-close"]`，说明依赖能感知并记录，然后 `raise` 保持原状态码。

### 4.4 清理阶段抛异常（实测）

`/bad-cleanup` 的生成器在 `yield` 后 `raise RuntimeError`：响应已是 200，`TestClient` 不抛（`raise_server_exceptions=False`），但服务端会记录异常。**结论**：清理代码必须自己 try/except。

### 4.5 嵌套顺序（实测）

`outer`/`inner` 两个生成器依赖 → 清理 `inner-close → outer-close`（后进先出，与 `ExitStack` 语义一致）。

### 4.6 校验失败时

参数校验失败发生在依赖解析之后/之间；已创建的生成器会走清理。本章的 `check_cleanup_on_validation_error` 实际走的是正常路径（无额外参数），真正的 422 场景**未单独实测**，结论按 `ExitStack` 语义推断。

### 4.7 与 `return` 依赖混用

普通函数依赖可用于同一路由，只是没有清理语义（实测 `{"v": "plain"}`）。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 忘写 `finally` | 异常时泄漏 | 一律 `finally` | 实测 |
| `yield` 后 `return` | 跳过清理 | 用 `finally` | `[Y1]` |
| 清理阶段抛异常 | 状态码改不了 | 内部 try/except | 实测 |
| `except: pass` | 吞错误 | `raise` | `[Y2]` |
| `yield` 前 `commit` | 事务过早 | `yield` 后提交 | `[Y3]` |
| 普通函数冒充清理依赖 | 清理不执行 | 生成器 | 实测 |
| `finally` 里做重 IO | 拖慢响应 | 轻量清理 | `[Y3]` |
| `async` 依赖用 `Iterator` | 类型不符 | `AsyncIterator` | `[Y1]` |
| 重复 `close` | 可能报错 | 幂等关闭 | `[Y3]` |
| 用 `yield` 依赖跑后台任务 | 资源已关 | 第 50 章 | `[Y3]` |
| 依赖里改 `response` 未注入 | 拿不到 | 参数注入 `Response` | 第 24 章 |
| 清理依赖里再 `yield` 依赖 | 顺序复杂 | 明确 LIFO | 实测 |
| 用生成器返回值做类型注解 | 提示错 | `Iterator[T]` | `[Y1]` |
| 在 `finally` 里 `raise` | 覆盖原异常 | 记录后吞 | 实测 |
| 依赖里 `await` 但函数非 async | 语法错 | `async def` | `[Y1]` |
| 清理依赖被多处 `Depends` | 只创建一次 | 依赖缓存 | 第 37 章 |
| 清理依赖里存全局状态 | 并发串数据 | 用实例/闭包 | `[Y2]` |
| 连接池耗尽未设超时 | 请求堆积 | 池大小+超时 | `[Y3]` |
| 在清理里再 `yield` 同名依赖 | 重复创建/顺序乱 | 拆成两个依赖 | `[Y3]` |

## 6. 最佳实践与编码建议

### 6.1 会话模板

```python
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends


async def get_session() -> AsyncIterator[Session]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[Session, Depends(get_session)]
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 一律 `try/finally` | 最稳 |
| 提交放 `else` | 只有成功才提交 |
| 清理短小 | 别做网络请求 |
| 清理幂等 | 重试安全 |
| 用别名复用 | 第 38 章 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 连接/会话 | `yield` 依赖 |
| 临时文件 | `yield` + `finally` 删除 |
| 锁 | `yield` + `finally` 释放 |
| 需要返回值 | `yield` 前构造 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[Y1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/dependencies/dependencies-with-yield/ | `yield` 依赖 |
| `[Y2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/dependencies/dependencies-with-yield/#dependencies-with-yield-and-except | 异常处理 |
| `[Y3]` | 参考 | https://docs.sqlalchemy.org/en/20/orm/session_basics.html | 会话生命周期 |

> **核对状态**：`[Y1]`–`[Y3]` 为官方/参考链接，**本次未逐页直连复核**；`open→commit→close`、异常 rollback、LIFO 清理、`athrow` 捕获、清理异常不改状态码、async 生成器均为本机实测，`examples/verify.py` 复现 12/12 通过。422 场景下的清理**未单独实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 三段式生命周期
- [ ] 清理相对响应的时序
- [ ] 异常如何进入依赖
- [ ] LIFO 顺序的来源
- [ ] 清理阶段异常的后果

**能写出（代码层）**：

- [ ] 会话依赖模板
- [ ] 异常回滚
- [ ] 嵌套依赖
- [ ] async 生成器
- [ ] 依赖内捕获并记录

**能判断（避坑层）**：

- [ ] 看到没有 `finally` → 指出泄漏
- [ ] 看到 `yield` 后 `return` → 指出跳过清理
- [ ] 看到清理里 `raise` → 指出改不了状态码
- [ ] 看到 `except: pass` → 指出吞错
- [ ] 看到 `yield` 前 commit → 指出过早提交

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 12/12
- [ ] `/session` 与 `/session/crash` 对比 LOG
- [ ] `/nested` 看 LIFO

## 9. 下一章衔接

第 41 章 `依赖覆盖`：`app.dependency_overrides[real] = fake` 在测试里替换数据库/外部服务，讲覆盖的匹配规则（按 callable 对象）、清理时机（`try/finally` 或 fixture）、覆盖 `yield` 依赖的注意事项。

本章留下的伏笔：

1. 测试替换 第 41 章。
2. 分页实战 第 42 章。
3. 鉴权实战 第 43 章。
4. 后台任务 第 50 章。