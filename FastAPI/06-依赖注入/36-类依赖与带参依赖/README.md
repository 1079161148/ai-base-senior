# 36 类依赖与带参依赖

## 一句话结论

依赖可以是任何**可调用对象**，但语义不同：`Depends(类)` → 框架解析 `__init__` 签名并**注入实例**（不自动调 `__call__`，实测：注解写 `dict` 会因返回对象而 500）；`Depends(实例)` → 调用 `obj.__call__()`，`__init__` 的配置被焊死、**不出现在 OpenAPI**；`Depends(factory(x))` → 用闭包把配置藏起来，只暴露被依赖的头/query。

学完这一章，你能：用类写可配置分页器、用实例写限流器、用工厂生成多个「同构不同配」的依赖。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import Depends, FastAPI, Query

app = FastAPI()


class CommonQueryParams:
    def __init__(
        self,
        q: Annotated[str | None, Query()] = None,
        skip: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 10,
    ) -> None:
        self.q, self.skip, self.limit = q, skip, limit


@app.get("/items")
def list_items(commons: Annotated[CommonQueryParams, Depends()]) -> dict:
    return {"q": commons.q, "skip": commons.skip, "limit": commons.limit}


def require_header(name: str, expected: str = "ok"):
    def dependency(value: Annotated[str | None, __import__("fastapi").Header(alias=name)] = None) -> str:
        if value != expected:
            raise __import__("fastapi").HTTPException(400, f"{name} 缺失或错误")
        return value

    return dependency


@app.get("/factory")
def use_factory(key: Annotated[str, Depends(require_header("X-Api-Key"))]) -> dict:
    return {"key": key}
```

完整版本（实例限流器、类 vs 实例对比、工厂截断 limit）见 `examples/main.py`。

## 怎么跑

```powershell
cd "06-依赖注入\36-类依赖与带参依赖\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 类作依赖 -> ids=[3, 4, 5]
[PASS] 类参数进 OpenAPI -> parameters=['q', 'skip', 'limit']
[PASS] 类依赖校验 -> limit=0 → 422（loc=query,limit）
[PASS] 实例作依赖（固定） -> size 固定 3，OpenAPI 无参数
[PASS] 类作依赖（可配） -> ?size=5 → {'size': 5}（注入实例而非 __call__ 结果）
[PASS] 类 vs 实例语义 -> Cls → 实例；obj → __call__ 结果
[PASS] __call__ 签名不外露 -> 限流器无 query 参数
[PASS] 限流器 429 -> 200,200,429 + Retry-After=60
[PASS] 工厂依赖 A -> 错误 400 / 正确 200
[PASS] 工厂依赖 B -> X-Admin-Token=admin 通过
[PASS] 工厂截断 limit -> size 被截到 5，page=3
[PASS] 配置不入 OpenAPI -> 配置参数只留在闭包里
[PASS] lambda 依赖 -> lambda 依赖返回 42

结果：13/13 通过
```

## 核心 API 速查

| 写法 | 框架做什么 | 注入什么 | OpenAPI |
| --- | --- | --- | --- |
| `Depends(Cls)` | 解析 `__init__` 并构造 | **实例** | `__init__` 参数 |
| `Depends(obj)` | 调用 `obj.__call__()` | 返回值 | `__call__` 参数 |
| `Depends()` + 注解 `Cls` | 同 `Depends(Cls)` | 实例 | `__init__` 参数 |
| `Depends(factory(x))` | 调用返回的闭包 | 返回值 | 闭包参数 |
| `Depends(lambda: 42)` | 直接调用 | 返回值 | 无 |

| 实测行为 | 结果 |
| --- | --- |
| 类作依赖 + 注解写 `dict` | 500 `ResponseValidationError`（拿到的是实例）|
| 实例作依赖 | `__init__` 参数**不**进 OpenAPI，`size` 固定 |
| 类作依赖 | `?size=5` 生效，OpenAPI 有 `size` |
| `__call__(self, request)` | `request` 不进 OpenAPI、不需客户端提供 |
| `Header(alias="X-Api-Key")` | OpenAPI 参数名保留**原始大小写** `X-Api-Key` |
| 工厂配置值 | 不出现在 OpenAPI |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `Depends(Cls)` 后按 dict 用 | 500（拿到实例）| 用属性或改注入 `obj.__call__` |
| 以为类依赖会自动调 `__call__` | 拿到对象 | 实例作依赖才调 |
| 实例作依赖却想改配置 | 改不动（已固定）| 用类或工厂 |
| 用类作依赖传配置 | 配置变成 query 参数 | 用实例/工厂焊死 |
| 限流器计数用全局变量 | 多 app 串数据 | 用实例属性 |
| 限流器多进程部署 | 每个 worker 各算一份 | 用 Redis |
| 工厂闭包里再声明 `Depends` 参数 | 可以，但要注意缓存 | 第 37 章 |
| 类依赖 `__init__` 里做 IO | 每次请求都执行 | 移到 `__call__`/服务层 |
| `Depends(lambda: obj)` 返回大对象 | 每请求构造 | 返回轻量值 |
| 忘记 `from __future__` 与局部类 | 注解解析失败 | 类定义在模块级 |

## 毕业自查

- [ ] 能说出「类作依赖」与「实例作依赖」的差别
- [ ] 能写出 `__init__` 参数进 OpenAPI 的类依赖
- [ ] 能用实例写一个限流器
- [ ] 能用工厂生成两个不同配置的依赖
- [ ] 能解释为什么工厂配置不出现在 OpenAPI
- [ ] 动手题一：把限流器改成滑动窗口
- [ ] 动手题二：用类依赖实现「资源必须存在否则 404」

> 想看 `Depends` 对可调用对象的分支判断、`__call__` 签名分析、实例状态与并发的风险、18 条坑，继续读 [`base.md`](./base.md)。