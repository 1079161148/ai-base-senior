# 35 第一个依赖项（Depends）

## 一句话结论

`Depends(fn)` 把「多个端点都要用的参数解析」抽成一个函数：框架先解析 `fn` 的参数（**它们照样进 OpenAPI**，实测 `/items` 出现 `q/skip/limit` 三个 query 参数），再把返回值注入端点。依赖里 `raise HTTPException` 时**路由函数根本不执行**；依赖返回的 dict 也不会变成 `requestBody`。

学完这一章，你能：抽出分页依赖、让依赖读 `Request`、在依赖里做鉴权、理解依赖参数与端点参数在 OpenAPI 里完全同权。

## 最小可运行案例

```python
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Query

app = FastAPI()


async def common_parameters(
    q: Annotated[str | None, Query(max_length=50)] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict[str, Any]:
    return {"q": q, "skip": skip, "limit": limit}


@app.get("/items")
def list_items(commons: Annotated[dict[str, Any], Depends(common_parameters)]) -> dict[str, Any]:
    return commons


@app.get("/users")
def list_users(commons: Annotated[dict[str, Any], Depends(common_parameters)]) -> dict[str, Any]:
    return commons
```

两个端点自动获得 `?q=&skip=&limit=`，`/docs` 里也能看到。

完整版本（依赖抛 401、依赖读 `Request`、路径参数共存）见 `examples/main.py`。

## 怎么跑

```powershell
cd "06-依赖注入\35-第一个依赖项\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 默认值 -> 默认 params={'q': None, 'skip': 0, 'limit': 10}
[PASS] 传参生效 -> skip=5 limit=3 → first=6
[PASS] 依赖内校验 -> 422 loc=['query', 'limit']
[PASS] 跨端点复用 -> 另一个端点自动获得 q/skip/limit
[PASS] 依赖抛 401 -> 401 且路由未执行
[PASS] 返回值注入 -> token 注入成功
[PASS] 依赖读 Request -> ua=verify/35, path=/client
[PASS] OpenAPI 参数来源 -> parameters=['q', 'skip', 'limit']，description 保留
[PASS] 无 requestBody -> GET /items 无 requestBody
[PASS] async 依赖 -> common_parameters / client_info 均为 async
[PASS] 路径参数共存 -> item_id=7 + limit=2
[PASS] Depends 复用 -> 两次请求各调用一次（累计 2）

结果：12/12 通过
```

## 核心 API 速查

| 写法 | 说明 |
| --- | --- |
| `Annotated[T, Depends(fn)]` | 现代写法，推荐 |
| `param: T = Depends(fn)` | 旧写法，等价 |
| `Depends()` | 不加 callable 会报错，必须给函数/类 |
| 依赖函数签名 | 与端点签名同权：可有 `Query`/`Header`/`Request` |
| 返回值 | 任意对象，直接注入参数 |

| 实测行为 | 结果 |
| --- | --- |
| 依赖参数进 OpenAPI | `parameters = [q, skip, limit]`，`in: query` |
| 依赖返回值 | 不产生 `requestBody` |
| 依赖里校验失败 | 422，`loc` 是 `["query","limit"]` |
| 依赖里抛 401 | 401，路由体内代码不执行 |
| 同一依赖用于两个端点 | 各自独立展开 |
| 每请求调用次数 | 一次（跨请求不缓存，见第 37 章）|
| `async def` 依赖 | 支持 |
| `Request` 注入 | 依赖可独吞，端点签名不出现 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `Depends()` 不给函数 | 定义期报错 | `Depends(fn)` |
| `Annotated[dict, Depends(fn)] = {}` | 默认值被忽略/冲突 | 默认值写在 `fn` 参数上 |
| 以为依赖参数要自己解析 | 重复读 query | 直接声明类型 |
| 依赖返回大对象 | 每请求都构造 | 用缓存/`use_cache`（第 37 章）|
| 依赖里做重 IO | 拖慢所有端点 | 只做必要解析 |
| 依赖里 `return` 错误信息 | 路由继续执行 | `raise HTTPException` |
| 依赖里写模块级状态 | 并发串数据 | 用 `request.state` |
| 把依赖当中间件用 | 顺序/异常语义不同 | 明确用途（第 39 章）|
| 依赖参数名与端点参数名重复 | 以端点为准，易混淆 | 改名或合并 |
| 同步依赖里做阻塞 IO | 阻塞事件循环 | 用 `async def` 或线程池 |

## 毕业自查

- [ ] 能写出一个被两个端点复用的分页依赖
- [ ] 能说出依赖参数在 OpenAPI 里的位置
- [ ] 能解释依赖抛错时路由为什么不执行
- [ ] 能让依赖读 `Request` 而不污染端点签名
- [ ] 能说出 `Annotated[..., Depends()]` 与 `= Depends()` 的关系
- [ ] 动手题一：加 `sort` 参数并限制枚举
- [ ] 动手题二：给分页依赖加「最大 limit」并返回 422

> 想看依赖的解析顺序、`Depends` 的内部结构（`dependant`）、参数合并规则、18 条坑，继续读 [`base.md`](./base.md)。