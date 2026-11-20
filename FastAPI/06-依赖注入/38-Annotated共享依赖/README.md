# 38 Annotated 共享依赖

## 一句话结论

`type CommonsDep = Annotated[CommonQueryParams, Depends()]` 把「类型 + 依赖」打包成一个名字，端点只写 `commons: CommonsDep`。实测：别名就是 `TypeAliasType`，`__value__` 里是 `Annotated[T, Depends(...)]`；与内联写法生成**完全一致**的 OpenAPI；但 `Depends(CommonsDep)` 会 `TypeError: CommonsDep is not a callable object`——别名只能用在参数注解位置。

学完这一章，你能：全项目复用依赖别名、跨模块 import、避免每个端点重复 `Depends(...)`。

## 最小可运行案例

```python
from typing import Annotated, Any

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


# Python 3.12 的 type 语句
type CommonsDep = Annotated[CommonQueryParams, Depends()]


@app.get("/items")
def list_items(commons: CommonsDep) -> dict[str, Any]:
    return {"skip": commons.skip, "limit": commons.limit}


@app.get("/users")
def list_users(commons: CommonsDep) -> dict[str, Any]:
    return {"limit": commons.limit}
```

完整版本（`UserDep`/`AdminDep` 嵌套、401/403）见 `examples/main.py`。

## 怎么跑

```powershell
cd "06-依赖注入\38-Annotated共享依赖\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 别名展开参数 -> 别名 → q/skip/limit
[PASS] 别名复用 -> 两个端点参数一致
[PASS] TypeAliasType -> CommonsDep 类型 = TypeAliasType
[PASS] __value__ 结构 -> value = Annotated[CommonQueryParams, Depends(...)]
[PASS] 运行时真实类型 -> UserDep → dict
[PASS] 401 -> 401 + challenge
[PASS] 嵌套别名 -> bob→403, alice→200
[PASS] 别名 + 自有参数 -> parameters=['detail', 'X-User']
[PASS] Depends(别名) 失败 -> TypeError: CommonsDep is not a callable object
[PASS] 与内联等价 -> 别名与内联 OpenAPI 完全一致
[PASS] 跨模块引用 -> from main import CommonsDep 可用

结果：11/11 通过
```

## 核心 API 速查

| 写法 | 说明 |
| --- | --- |
| `type XDep = Annotated[T, Depends(fn)]` | Python 3.12+，**推荐** |
| `XDep = Annotated[T, Depends(fn)]` | 3.8–3.11 的写法，运行时等价 |
| `x: XDep` | 端点签名使用 |
| `Depends(XDep)` | **错误**，别名不可调用 |
| `from deps import XDep` | 跨模块复用 |

| 实测行为 | 结果 |
| --- | --- |
| 别名类型 | `TypeAliasType` |
| `__value__` | `Annotated[CommonQueryParams, Depends(...)]` |
| 运行时拿到的值 | 真实对象（`dict`/类实例） |
| 与内联写法的 OpenAPI | 完全一致 |
| `Depends(别名)` | `TypeError: ... is not a callable object` |
| 参数顺序 | query 在前、header 在后，不按源码顺序 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `Depends(CommonsDep)` | `TypeError` 不可调用 | 别名只放注解 |
| 以为别名能当类型断言 | `isinstance(x, CommonsDep)` 报错 | 用底层类型 |
| 在 3.11 用 `type` 语句 | SyntaxError | 用普通赋值 |
| 别名里重复写约束 | 与底层冲突 | 约束放依赖函数 |
| 一个别名塞两种依赖 | 语义混乱 | 拆开 |
| 跨模块循环 import | ImportError | 依赖定义放独立模块 |
| 别名命名与真实类型混淆 | 读代码困惑 | `XxxDep` 后缀 |
| 以为别名会做缓存 | 缓存仍按 callable | 第 37 章 |
| 别名里用 `Depends()` 空参却注解不是类 | 定义期报错 | 明确 `Depends(Cls)` |
| 路径参数用 `Query(...)` 带约束 | 定义期 `AssertionError` | 用 `Path(...)` |

## 毕业自查

- [ ] 能写出 `type XDep = Annotated[T, Depends(fn)]` 并解释
- [ ] 能说明别名与内联写法等价
- [ ] 能说出 `Depends(别名)` 为什么失败
- [ ] 能跨模块复用别名
- [ ] 能用别名做嵌套（`AdminDep`）
- [ ] 动手题一：把 `CommonsDep` 拆成 `SearchDep` 与 `PageDep`
- [ ] 动手题二：给别名加 `use_cache=False` 变体并说明风险

> 想看 `TypeAliasType` 与 `Annotated` 的元数据解析、别名在各版本 Python 的写法、18 条坑，继续读 [`base.md`](./base.md)。