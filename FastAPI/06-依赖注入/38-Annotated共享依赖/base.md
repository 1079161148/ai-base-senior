# 38 Annotated 共享依赖 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「`Annotated` 的元数据怎么被解析、`type` 别名在运行时是什么、为什么不能 `Depends(别名)`、跨模块怎么组织」拆开。学完这章，你要能把依赖声明收敛成一组可 import 的类型别名。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Python 3.12+（本机实测） |
| 前置 | 第 35–37 章（`Depends`、类依赖、缓存） |
| 覆盖范围 | `type` 别名、`Annotated` 元数据、`TypeAliasType`、跨模块复用、等价性 |
| 明确不覆盖 | 泛型依赖、`Annotated` 与 Pydantic 元数据混用细节 |
| 学完验收 | 能跑通 `verify.py` 11/11、能写出别名模块、能解释 `TypeError` 原因 |

## 0. 怎么用这份文件

**依据约定**：`` `[An]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 别名解决什么
2 机制（第 2 节）    → Annotated 元数据 + TypeAliasType
3 API（第 3 节）     → 写法、组合、跨模块
4 边界（第 4 节）    → 不可调用、版本、顺序、等价性
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 别名模块模板
```

## 1. 概念：别名是「参数声明的宏」

| 没有别名 | 有别名 |
| --- | --- |
| 每个端点写 `Annotated[CommonQueryParams, Depends()]` | 写 `CommonsDep` |
| 改依赖类型要改 N 处 | 改一处 |
| 类型信息与依赖分散 | 打包 |
| 新人不知道有哪些共享依赖 | 一个模块看完 |

别名**不是**新类型：运行时 `commons` 仍是 `CommonQueryParams` 实例。

## 2. 机制：`Annotated` 与 `TypeAliasType`

```python
type CommonsDep = Annotated[CommonQueryParams, Depends()]
```

| 层 | 运行时的样子 |
| --- | --- |
| `CommonQueryParams` | 普通类 |
| `Annotated[Cls, meta]` | `typing.Annotated` 对象，`get_args` → `(Cls, meta)` |
| `CommonsDep` | `TypeAliasType` 实例，`__value__` 指向上面那个 |

框架拿到注解后：

```text
get_origin(注解析) → Annotated
get_args(...) → (T, *metadata)
metadata 里有 Depends → 按依赖处理，T 作为注入类型
```

实测 `Depends(CommonsDep)` → `TypeError: CommonsDep is not a callable object`，因为 `TypeAliasType` 没有 `__call__`。

## 3. API 逐个拆解

### 3.1 三种写法

| 写法 | 版本 | 说明 |
| --- | --- | --- |
| `type XDep = Annotated[T, Depends(f)]` | 3.12+ | **推荐**，延迟求值 |
| `XDep = Annotated[T, Depends(f)]` | 3.8+ | 运行时等价 |
| `XDep: TypeAlias = Annotated[...]` | 3.10+ | 显式标注，工具友好 |

### 3.2 常见别名

```python
type CommonsDep = Annotated[CommonQueryParams, Depends()]
type UserDep = Annotated[dict[str, Any], Depends(get_user)]
type AdminDep = Annotated[dict[str, Any], Depends(require_admin)]
```

| 别名 | 注入 | 失败码 |
| --- | --- | --- |
| `CommonsDep` | 实例 | 422 |
| `UserDep` | dict | 401/404 |
| `AdminDep` | dict | 403 |

### 3.3 组合

```python
@app.get("/me")
def me(user: UserDep, detail: Annotated[bool, Query()] = False) -> dict: ...
```

别名与自有参数、路径参数可共存；实测 `parameters = ['detail', 'X-User']`（query 在前）。

## 4. 边界条件

### 4.1 别名不可调用（实测）

`Depends(CommonsDep)` → `TypeError`。别名只能出现在**注解**位置。

### 4.2 与内联写法等价（实测）

同一依赖用别名 vs 内联 → OpenAPI `parameters` 完全一致，行为一致。

### 4.3 跨模块

```python
# deps.py
type UserDep = Annotated[dict[str, Any], Depends(get_user)]

# routers/users.py
from deps import UserDep

@app.get("/me")
def me(user: UserDep) -> dict: ...
```

注意避免 `deps.py` 反向 import `routers`（循环）。

### 4.4 运行时类型

`user: UserDep` 在函数体内是 `dict`，IDE 能提示 `.get()`；但 `isinstance(x, UserDep)` 会 `TypeError`。

### 4.5 别名里放多个元数据

`Annotated[T, Depends(f), Query(...)]` 的语义由框架决定，可能冲突。**未实测**组合行为，建议一个别名只放一个 `Depends`。

### 4.6 路径参数别用 `Query`（实测）

```python
item_id: Annotated[int, Query(ge=1)]   # 定义期 AssertionError
```

`AssertionError: Cannot use Query for path param 'item_id'`。用 `Path(ge=1)`。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `Depends(别名)` | `TypeError` | 别名只放注解 | 实测 |
| `isinstance(x, 别名)` | `TypeError` | 用底层类型 | 实测 |
| 3.11 用 `type` 语句 | SyntaxError | 普通赋值 | `[A1]` |
| 别名里再套约束 | 与底层冲突 | 约束放依赖函数 | `[A2]` |
| 循环 import | ImportError | 独立 `deps.py` | `[A3]` |
| 别名命名无 `Dep` 后缀 | 难辨类型/依赖 | 统一后缀 | `[A2]` |
| 以为别名会缓存 | 缓存按 callable | 第 37 章 | 实测 |
| `Depends()` 空参与注解不匹配 | 定义期报错 | `Depends(Cls)` | 实测 |
| 路径参数用 `Query` 带约束 | `AssertionError` | `Path` | 实测 |
| 一个别名塞两种依赖 | 语义混乱 | 拆分 | `[A2]` |
| 别名定义在端点文件里 | 无法跨模块复用 | 集中 `deps.py` | `[A3]` |
| 改别名签名无迁移说明 | 全站 API 变更 | 版本化/评审 | `[A2]` |
| 别名与模型同名 | 混淆 | 加后缀 | `[A2]` |
| 在别名里写默认值 | 冲突 | 默认值放依赖函数 | `[A1]` |
| 用别名做响应模型 | 语义不符 | 用模型类 | 第 21 章 |
| 别名层层嵌套无注释 | 难追踪 | 注释依赖链 | `[A2]` |
| 忽略参数顺序 | 断言失败 | 用集合/按规范断言 | 实测 |
| 别名在 `if TYPE_CHECKING` 里定义 | 运行时 NameError | 运行期可见 | `[A3]` |
| 别名里混入 `Body` 元数据 | 请求体行为难预期 | 一个别名一个依赖 | `[A2]` |

## 6. 最佳实践与编码建议

### 6.1 别名模块模板

```python
# app/deps.py
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Query


class Page:
    def __init__(self, skip: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=100)] = 10) -> None:
        self.skip, self.limit = skip, limit


def get_user(x_user: Annotated[str | None, Header(alias="X-User")] = None) -> dict[str, Any]:
    if x_user is None:
        raise HTTPException(401, "缺少 X-User")
    return {"name": x_user}


type PageDep = Annotated[Page, Depends()]
type UserDep = Annotated[dict[str, Any], Depends(get_user)]
```

| 建议 | 说明 |
| --- | --- |
| 统一放 `deps.py` | 单一入口 |
| 命名 `XxxDep` | 一眼识别 |
| 一个别名一个依赖 | 语义清晰 |
| 别名上写 docstring（可为注释）| 团队可见 |
| 变更走评审 | 这是公开契约 |

### 6.2 选型速查

| 场景 | 做法 |
| --- | --- |
| 临时用一次 | 内联 `Annotated` |
| 复用 ≥ 2 处 | 别名 |
| 跨模块 | `deps.py` |
| 需要配置 | 工厂 + 别名（第 36 章）|
| 整组路由统一 | 第 39 章 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[A1]` | 官方文档 | https://fastapi.tiangolo.com/zh/python-types/#type-hints-with-metadata-annotations | `Annotated` 语义 |
| `[A2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/dependencies/ | 依赖声明 |
| `[A3]` | 参考 | https://docs.python.org/3/library/typing.html#typing.TypeAliasType | `type` 语句 |

> **核对状态**：`[A1]`–`[A3]` 为官方/参考链接，**本次未逐页直连复核**；`TypeAliasType`、`__value__` 结构、`Depends(别名)` TypeError、与内联 OpenAPI 等价、参数顺序、路径参数 `Query` 报错均为本机实测，`examples/verify.py` 复现 11/11 通过。多元数据组合**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 别名与内联写法的关系
- [ ] `Annotated` 元数据如何被解析
- [ ] `TypeAliasType` 与普通对象的差别
- [ ] 为什么 `Depends(别名)` 失败
- [ ] 别名的作用域（编译期 vs 运行时）

**能写出（代码层）**：

- [ ] `type CommonsDep = ...`
- [ ] `UserDep`/`AdminDep` 嵌套
- [ ] 跨模块 import
- [ ] 别名 + 自有参数

**能判断（避坑层）**：

- [ ] 看到 `Depends(别名)` → 指出 TypeError
- [ ] 看到 `isinstance(x, 别名)` → 指出报错
- [ ] 看到 3.11 `type` 语句 → 指出语法错
- [ ] 看到别名里塞约束 → 指出冲突
- [ ] 看到路径参数用 `Query` → 指出定义期报错

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 11/11
- [ ] `/docs` 看别名参数
- [ ] `python -c "import main; print(type(main.CommonsDep))"`

## 9. 下一章衔接

第 39 章 `装饰器与全局依赖`：`@app.get(..., dependencies=[Depends(auth)])` 给单个端点加依赖、`APIRouter(dependencies=[...])` 给一组路由加、`FastAPI(dependencies=[...])` 全局加，以及它们与参数注入的差别——**用 `dependencies=` 时拿不到返回值**。

本章留下的伏笔：

1. 整组路由统一鉴权 第 39 章。
2. 全局依赖与中间件边界 第 39 章。
3. `yield` 清理 第 40 章。
4. 测试替换 第 41 章。