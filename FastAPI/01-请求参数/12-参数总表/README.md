# 12 参数总表

## 一句话结论

路径 / 查询 / 请求头 / Cookie 是**四个不同的取值位置**，不是四种数据类型：同一个名字出现在不同位置**不会互相覆盖**，因为 FastAPI 按声明的位置去对应容器里取。真正的冲突是「声明位置」与「路径模板」不一致——那是**导入期直接报错**。`Request` 直取是绕过校验的旁路，只在这四类参数表达不了时才用。

学完这一章，你能：一个接口同时收四类参数、说清同名为什么能共存、识别 `Path()` 幽灵参数、判断什么时候该用 `Request`。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import Cookie, FastAPI, Header, Path, Query, Request

app = FastAPI()


@app.get("/summary/{item_id}")
def summary(
    item_id: Annotated[int, Path(ge=1)],           # in=path（名字在模板里）
    request: Request,                               # 绕过校验的旁路
    q: Annotated[str | None, Query()] = None,       # in=query
    x_token: Annotated[str | None, Header()] = None,  # in=header，对应 X-Token
    sid: Annotated[str | None, Cookie()] = None,    # in=cookie
) -> dict[str, object]:
    return {
        "typed": {"item_id": item_id, "q": q, "x_token": x_token, "sid": sid},
        "raw": {"path": dict(request.path_params), "query": dict(request.query_params)},
    }
```

完整版本（同名四位置、幽灵参数陷阱、错误聚合）见 `examples/main.py`。

## 怎么跑

```powershell
cd "01-请求参数\12-参数总表\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 四类参数同时生效 -> {'item_id': 7, 'q': 'hello', 'x_token': 'tk', 'sid': 's1'}
[PASS] raw 与 typed 的差异 -> typed=7 / raw={'item_id': '7'}
[PASS] OpenAPI 四种 in -> path/query/header/cookie 四种 in 齐全，request 未出现
[PASS] 同名参数互不干扰 -> {'path': 'pathval', 'query': 'queryval', 'header': 'headerval', 'cookie': 'cookieval'}
[PASS] Request 直取不校验 -> limit_raw="abc" / q_get="2" / getlist=["1","2"]
[PASS] 声明位置与模板冲突 -> Query->Cannot use `Query` for path param 'item_id' | Header->Cannot use `Header` for path param 'token' | default->Path parameters cannot have default values
[PASS] 幽灵路径参数永远 422 -> 422 missing loc=['path', 'x']
[PASS] 错误聚合 -> 3 条错误，loc 覆盖 path/header/query
[PASS] 只声明 Request 无 OpenAPI 参数 -> parameters 为空 → 文档上看不到参数
[PASS] 404 与 422 的边界 -> 类型失败 422（loc=path）；无路由 404

结果：10/10 通过
```

## 核心 API 速查

四类参数对照：

| 位置 | 声明方式 | `in` | 可选性由谁定 | 典型用途 |
| --- | --- | --- | --- | --- |
| 路径 | 名字在 `{...}` 里，可加 `Path()` | `path` | **恒必填**（无默认值，也不能有） | 资源标识 |
| 查询 | 不在模板里，可加 `Query()` | `query` | 有无默认值 | 过滤/分页/排序 |
| 请求头 | `Header()` | `header` | 有无默认值 | 鉴权/追踪/幂等 |
| Cookie | `Cookie()` | `cookie` | 有无默认值 | 会话 |

`Request` 常用属性：

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `request.path_params` | `dict[str, str]` | 路径参数原始值（**字符串**） |
| `request.query_params` | `QueryParams` | `.get()` 取最后一个，`.getlist()` 取全部 |
| `request.headers` | `Headers` | 大小写不敏感；`.get()` 取第一个，`.getlist()` 取全部 |
| `request.cookies` | `dict[str, str]` | Cookie 原始值 |
| `request.method` / `request.url` | `str` / `URL` | 方法、完整 URL |
| `request.client` | `Address \| None` | 对端地址（代理后需第 54 章配置） |
| `request.state` | `State` | 跨依赖/中间件传值（第 43 章） |

| 关键行为 | 事实 |
| --- | --- |
| 同名不同位置 | 各自取值，**没有覆盖链** |
| 模板参数声明成 `Query()`/`Header()` | 导入期 `AssertionError` |
| 模板参数给默认值 | 导入期 `AssertionError` |
| `Path()` 用在不存在的模板参数上 | 启动不报错，**永远 422** |
| `Request` 直取 | **不做任何校验/转换**，永远拿到字符串 |
| 多个参数同时非法 | 一个 422 里聚合全部错误 |
| `Request` 参数 | 不进 OpenAPI |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `Path()` 用在路由模板里没有的名字 | 启动正常，请求**永远 422** `loc=["path","x"]` | 名字与 `{x}` 对齐，或改 `Query()` |
| 模板参数写 `Query()` | `AssertionError: Cannot use Query for path param 'x'` | 模板里的只能是路径参数 |
| 模板参数给默认值 | `AssertionError: Path parameters cannot have default values` | 必填就写必填，可选移到查询参数 |
| 以为同名参数有优先级 | 实测四个位置各自取值 | 按「位置」理解，不要猜顺序 |
| 用 `Request` 替代类型标注 | `?limit=abc` 也 200，脏数据进业务 | 能标注就标注，`Request` 只做补充 |
| 依赖 `query_params.get()` 的多值顺序 | 取**最后一个**，与 `headers.get()`（取第一个）相反 | 多值一律 `getlist()` |
| 以为 `Request` 会出现在文档里 | OpenAPI 里没有它 | 需要文档就声明成 typed 参数 |

## 毕业自查

- [ ] 能说出四类参数对应的 `in` 值与可选性规则
- [ ] 能解释「同名不冲突」的原因（按位置取值，容器本身分开）
- [ ] 能背出「模板参数 + Query/Header/默认值」三条导入期错误
- [ ] 能识别 `Path()` 幽灵参数，并说明为什么永远 422
- [ ] 能说出 `request.path_params` 与 typed 参数的差异（字符串 vs 已转换）
- [ ] 能说出 `Request` 直取的两个代价（无校验、无文档）
- [ ] 动手题一：在 `/summary` 加一个 `lang` 查询参数，缺失时默认 `zh`
- [ ] 动手题二：把 `/raw` 的 `limit` 从字符串改成「非法值返回 400」

> 想看四类参数的完整机制、错误聚合顺序、`Request` 全部属性表、26 条坑，继续读 [`base.md`](./base.md)。
