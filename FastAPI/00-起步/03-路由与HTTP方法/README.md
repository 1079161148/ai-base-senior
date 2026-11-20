# 03 路由与 HTTP 方法

## 一句话结论

一个路由 = **路径 + 方法 + 处理函数**。FastAPI 按**注册顺序**从上往下匹配，第一个匹配上的就赢——所以 `/items/{item_id}` 写在 `/items/latest` 前面，`latest` 会被当成 `item_id="latest"` 吃掉。

学完这一章，你能：给一个资源写全 CRUD 路由、解释 405 与 404 的区别、说清「为什么我的精确路径不生效」。

## 最小可运行案例

```python
from fastapi import FastAPI, Response, status

app = FastAPI()
DB: dict[int, str] = {1: "苹果"}

# 【关键】精确路径必须写在通配路径之前
@app.get("/items/latest")
def latest() -> dict[str, str]:
    return {"latest": "苹果"}


@app.get("/items/{item_id}")
def detail(item_id: int) -> dict[str, object]:
    return {"id": item_id, "name": DB.get(item_id)}


@app.post("/items", status_code=status.HTTP_201_CREATED)
def create(name: str) -> dict[str, object]:
    new_id = max(DB) + 1 if DB else 1
    DB[new_id] = name
    return {"id": new_id, "name": name}


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(item_id: int) -> Response:
    DB.pop(item_id, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

完整版本（含 PUT/PATCH/HEAD/路径转换器）见 `examples/main.py`。

## 怎么跑

```powershell
cd "00-起步\03-路由与HTTP方法\examples"
uv run uvicorn main:app --reload

# 或不起服务直接验收
uv run python verify.py
```

预期输出：

```text
[PASS] 精确路径优先 -> {'latest': '苹果'}
[PASS] 路径参数类型转换 -> 200 {'id': 1, ...}
[PASS] 四种方法各自命中 -> POST/PUT/PATCH/DELETE 全 200
[PASS] 错误方法返回 405 且带 Allow -> 405 allow=GET
[PASS] 204 无响应体 -> 204 ''
[PASS] 路径转换器 :path -> a/b/c.txt
[PASS] include_in_schema=False 不进文档 -> 路由可用，openapi 无此路径
[PASS] url_path_for 反向解析 -> /items/9

结果：8/8 通过
```

## 核心 API 速查

| 装饰器 | 方法 | 幂等 | 有无请求体 | 典型状态码 |
| --- | --- | --- | --- | --- |
| `@app.get` | GET | ✅ | 无 | 200 |
| `@app.post` | POST | ❌ | 有 | 201 |
| `@app.put` | PUT | ✅ | 有（全量） | 200 / 204 |
| `@app.patch` | PATCH | ❌ | 有（部分） | 200 / 204 |
| `@app.delete` | DELETE | ✅ | 通常无 | 204 |
| `@app.head` | HEAD | ✅ | 无 | 200 |
| `@app.options` | OPTIONS | ✅ | 无 | 204 |
| `@app.api_route(path, methods=[...])` | 任意组合 | — | — | 自定义 |

| 参数 | 作用 |
| --- | --- |
| `path` | 必须以 `/` 开头 |
| `status_code` | 成功时返回的状态码（默认 200） |
| `name` | 反向解析用的路由名，默认取函数名 |
| `include_in_schema` | `False` 时路由可用但不进 `/docs` |
| `response_class` | 换响应类 |
| `tags` / `summary` / `description` / `deprecated` | 文档相关 |

| 路径写法 | 匹配示例 | 说明 |
| --- | --- | --- |
| `/items` | `/items` | 精确 |
| `/items/{id}` | `/items/1` | 单段，**不跨斜杠** |
| `/items/{id:int}` | `/items/1` | 显式转换器 |
| `/files/{p:path}` | `/files/a/b.txt` | 跨斜杠 |
| `/items/` | `/items/` | 注意尾斜杠 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `@app.get("/items/{item_id}")` 写在 `@app.get("/items/latest")` 之前 | 实测 `/items/latest` 返回 `{"matched":"param","value":"latest"}`——精确路径被吃掉 | 精确路径写在前面 |
| 认为 `@app.get` 会自动支持 HEAD | 实测 `HEAD /items` → **405**，`Allow: GET` | 用 `@app.api_route(..., methods=["GET","HEAD"])` |
| 多条路由重复注册同一路径+方法 | 实测**先注册的生效**，后一条永远不命中，但两条都在路由表里 | 避免重复，用 `routes` 表自查 |
| `DELETE` 返回 204 却写了 `return {...}` | 响应体被丢弃或报警告 | 返回 `Response(status_code=204)` |
| 用 `GET` 做删除 | 缓存、爬虫、预取都会误删 | 用 `DELETE` |
| 405 当成 404 排查 | 方向错 | 405 说明路径存在、方法不对，看 `Allow` 头 |
| `include_in_schema=False` 用在正式接口 | 前端不知道有这个接口 | 只用于内部/调试 |
| 忘记 `name` 导致反向解析混乱 | `url_path_for` 找不到 | 显式 `name="get-item"` |

## 毕业自查

- [ ] 能说出路由匹配的优先级规则，并解释为什么 `latest` 会被吃掉
- [ ] 能说出 404 / 405 / 422 的精确区别
- [ ] 能说出 `@app.get` 对 HEAD 的处理方式
- [ ] 能写出四种方法的完整 CRUD，并选对状态码
- [ ] 能说出 204 为什么不能有响应体
- [ ] 能用 `app.routes` 自查注册了哪些路由
- [ ] 能写出 `{file_path:path}` 的用途
- [ ] 动手题一：把 `/items/latest` 移到 `/items/{item_id}` 之后，验证行为变化
- [ ] 动手题二：用 `api_route` 让 `/health` 同时支持 GET 与 HEAD

> 想看匹配算法、Allow 头、路由表结构、36 条坑，继续读 [`base.md`](./base.md)。
