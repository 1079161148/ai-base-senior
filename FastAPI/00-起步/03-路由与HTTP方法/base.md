# 03 路由与 HTTP 方法 · 完整版（base.md）

> `README.md` 给你能抄的 CRUD；本文件把「路由表长什么样、匹配算法怎么走、为什么精确路径会被吃掉、405 的 Allow 头从哪来」拆开。学完这章，你要能看着 `app.routes` 说出一段 URL 会命中哪个函数。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Starlette 1.9.0 / Python 3.12.8（本机实测） |
| 前置 | 第 01 章（app 与装饰器）、`py-base/03-装饰器` |
| 覆盖范围 | 路由三元组、匹配算法、8 种方法装饰器、路径语法、状态码语义、405/204/HEAD、路由表与反向解析 |
| 明确不覆盖 | 请求参数类型与校验（05–12）、请求体（13）、`APIRouter` 拆分（04、65） |
| 学完验收 | 能跑通 `verify.py` 11/11、能解释 `latest` 被吃掉、能说出 405 与 404 的区别 |

## 0. 怎么用这份文件

**依据约定**：`` `[Rn]` `` 指向第 7 节；标「实测」的为本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 路由是什么、存在哪
2 机制（第 2 节）    → 匹配算法四步（重点）
3 API（第 3 节）     → 8 种装饰器 + 路径语法
4 边界（第 4 节）    → 顺序、405、HEAD、204、重复注册
5 注意事项（第 5 节）→ 36 条对照
6 最佳实践（第 6 节）→ REST 约定与命名
```

## 1. 概念：路由 = 路径 + 方法 + 函数

```python
@app.get("/items/{item_id}")
def get_item(item_id: int) -> dict: ...
```

这一行做了三件事：

| 动作 | 结果 | 依据 |
| --- | --- | --- |
| 创建 `APIRoute` 对象 | 含 `path`、`path_regex`、`methods`、`endpoint`、`dependant` | `[R1]` `[R3]` |
| 编译路径为正则 | `/items/{item_id}` → `^/items/(?P<item_id>[^/]+)$` | `[R3]` |
| 追加进 `app.routes` 列表 | **有序**，顺序即优先级 | `[R3]` |

`app.routes` 实测内容（`api_route` 那个例子）：

```text
[('/openapi.json', ['GET', 'HEAD']),
 ('/docs', ['GET', 'HEAD']),
 ('/docs/oauth2-redirect', ['GET', 'HEAD']),
 ('/redoc', ['GET', 'HEAD']),
 ('/multi', ['GET', 'HEAD', 'POST'])]
```

| 观察 | 结论 | 依据 |
| --- | --- | --- |
| 前 4 条是内置的 | FastAPI 自动注册了文档与契约路由 | `[R1]` |
| 内置路由都带 `HEAD` | 框架自己的路由支持 HEAD | 实测 |
| 你的路由默认只有 `GET` | `@app.get` 不隐含 HEAD | 实测 |
| 列表顺序 = 注册顺序 | 决定匹配优先级 | `[R3]` |

> 注意：「路由表是有序列表」这一条是整个章节的根。所有「我的精确路径不生效」的问题，根源都是它。

## 2. 机制：匹配算法四步

```text
收到请求 (method, path)
  ↓
① 遍历 app.routes，逐个用 path_regex.match(path)
  ↓ 命中
② 检查 method 是否在 route.methods 里
  ├─ 在  → Match.FULL  → 调用 endpoint
  └─ 不在 → Match.PARTIAL（记住这个 route）
  ↓ 遍历完都没 FULL
③ 如果有 PARTIAL → 405 Method Not Allowed + Allow 头
④ 没有任何 PARTIAL → 404 Not Found
```

| 步骤 | 代码位置 | 依据 |
| --- | --- | --- |
| ① | `Starlette.Router.__call__` → `route.matches(scope)` | `[R3]` |
| ② | `Match.FULL` / `Match.PARTIAL` | `[R3]` |
| ③ | `405` + `Allow` 响应头 | `[R3]` |
| ④ | `404` | `[R3]` |

### 2.1 为什么精确路径会被吃掉

实测两个 app，只是注册顺序不同：

```python
# 顺序 A：通配在前
@app.get("/items/{item_id}")
def by_id(item_id: str): return {"matched": "param", "value": item_id}

@app.get("/items/latest")
def latest(): return {"matched": "latest"}
```

```text
ORDER GET /items/latest    -> 200 {'matched': 'param', 'value': 'latest'}
ORDER GET /items/123       -> 200 {'matched': 'param', 'value': '123'}
```

```python
# 顺序 B：精确在前
@app.get("/items/latest")
def latest2(): return {"matched": "latest"}

@app.get("/items/{item_id}")
def by_id2(item_id: str): return {"matched": "param", "value": item_id}
```

```text
FIXED GET /items/latest    -> 200 {'matched': 'latest'}
FIXED GET /items/123       -> 200 {'matched': 'param', 'value': '123'}
```

| 结论 | 说明 |
| --- | --- |
| 顺序 A 下 `/items/latest` **永远不可达** | 被 `{item_id}` 匹配成 `"latest"` |
| 顺序 B 下两者都正确 | 精确 `str` 正则先匹配 |
| **框架不会自动优化优先级** | 必须人工排序 |

> 注意：这类 bug 极其隐蔽——接口不报错、返回 200，只是数据不对。排查方法：`items/{item_id}` 里打印 `item_id`，看到 `"latest"` 就懂了。`[R3]`

### 2.2 为什么 `/items/abc` 是 422 而不是 404

| 阶段 | 结果 |
| --- | --- |
| 路径正则 `^/items/(?P<item_id>[^/]+)$` 匹配 `/items/abc` | ✅ 匹配 |
| 方法 `GET` 在 `methods` 里 | ✅ |
| 参数转换 `int("abc")` | ❌ 失败 → **422** |

```text
GET /items/abc -> 422 {"detail": [{"type": "int_parsing", "loc": ["path", "item_id"], ...}]}
```

| 状态码 | 含义 | 什么时候 |
| --- | --- | --- |
| 404 | 没有路由匹配 | 路径不存在 |
| 405 | 路径匹配但方法不对 | `Allow` 头告诉你该用什么 |
| 422 | 路径与方法都对，参数不合法 | 类型转换或校验失败 |

## 3. API 逐一拆解

### 3.1 八种方法装饰器

| 装饰器 | 语义 | 幂等 | 有请求体 | 语义化状态码 | 依据 |
| --- | --- | --- | --- | --- | --- |
| `@app.get` | 读取 | ✅ | 无 | 200 | `[R2]` |
| `@app.post` | 创建 | ❌ | 有 | 201 | `[R2]` |
| `@app.put` | 全量替换 | ✅ | 有 | 200/204 | `[R2]` |
| `@app.patch` | 部分更新 | ❌ | 有 | 200 | `[R2]` |
| `@app.delete` | 删除 | ✅ | 通常无 | 204 | `[R2]` |
| `@app.head` | 只取头 | ✅ | 无 | 200 | `[R2]` |
| `@app.options` | 探测支持 | ✅ | 无 | 204 | `[R2]` |
| `@app.trace` | 回显 | ✅ | 无 | 200 | `[R2]` |
| `@app.api_route(path, methods=[...])` | 任意组合 | — | — | 自定义 | `[R2]` |

实测四种方法默认状态码：

```text
POST    -> 200 {'op': 'create'}
PUT     -> 200 {'op': 'replace'}
PATCH   -> 200 {'op': 'patch'}
DELETE  -> 200 {'op': 'delete'}
GET /res -> 405 POST
```

| 结论 | 说明 |
| --- | --- |
| 默认全是 **200** | 想语义化必须显式声明 `status_code` |
| `GET /res` → 405 | 该路径只注册了 POST/PUT/PATCH/DELETE |
| `Allow` 只显示 `POST` | 实测只返回第一个方法名，不要依赖它枚举全部 |

### 3.2 路由参数

| 参数 | 类型 | 默认 | 作用 | 依据 |
| --- | --- | --- | --- | --- |
| `path` | `str` | 必填 | 必须以 `/` 开头 | `[R2]` |
| `status_code` | `int` | `200` | 成功状态码 | `[R2]` |
| `name` | `str` | 函数名 | 反向解析键 | `[R1]` |
| `include_in_schema` | `bool` | `True` | 是否进 OpenAPI | `[R2]` |
| `response_class` | `type[Response]` | `JSONResponse` | 响应类 | `[R2]` |
| `tags` | `list[str]` | `None` | 文档分组 | `[R2]` |
| `summary` | `str` | 函数名 | 文档摘要 | `[R2]` |
| `description` | `str` | docstring | 文档描述 | `[R2]` |
| `deprecated` | `bool` | `False` | 标记废弃 | `[R2]` |
| `operation_id` | `str` | 自动 | 生成客户端的函数名 | `[R8]` |

### 3.3 路径语法

| 写法 | 正则 | 匹配 | 不匹配 |
| --- | --- | --- | --- |
| `/items` | `^/items$` | `/items` | `/items/`、`/items/1` |
| `/items/` | `^/items/$` | `/items/` | `/items`（307 重定向） |
| `/items/{id}` | `^/items/[^/]+$` | `/items/1`、`/items/abc` | `/items/1/2` |
| `/items/{id:int}` | `^/items/[0-9]+$` | `/items/1` | `/items/abc` → 404 |
| `/files/{p:path}` | `^/files/(?P<p>.*)$` | `/files/a/b.txt` | — |
| `/a/{x}/b/{y}` | 两段独立 | `/a/1/b/2` | `/a/1/2` |

内置转换器（Starlette 提供）：

| 转换器 | 正则 | 说明 |
| --- | --- | --- |
| `str`（默认） | `[^/]+` | 不含斜杠的任意字符 |
| `int` | `[0-9]+` | 纯数字 |
| `float` | `[0-9]+(\.[0-9]+)?` | 小数 |
| `uuid` | UUID 格式 | 标准 UUID |
| `path` | `.*` | 含斜杠 |

> 注意：`{id:int}` 与「参数标注 `int`」不是一回事。`{id:int}` 在**正则层面**就不匹配 `abc`（直接 404）；标注 `int` 是**匹配后再转换**，失败返回 422。生产上更推荐 `{id:int}`——让 404 更准确。`[R3]`

### 3.4 反向解析 `url_path_for`

```python
app.url_path_for("get_item", item_id=9)   # -> '/items/9'
```

实测（带一级前缀）：

```text
URL_FOR: /api/v1/things/42
```

| 用途 | 说明 | 依据 |
| --- | --- | --- |
| 生成跳转地址 | 重定向时不必拼字符串 | `[R1]` |
| 测试断言 | 避免硬编码路径 | `[R1]` |
| 模板里生成链接 | 前端路由变化只改一处 | `[R1]` |

> 注意：`name` 在同一 app 内应唯一。两个函数同名会让 `url_path_for` 命中第一个，且 OpenAPI 出现 `Duplicate Operation ID` 警告（见 4.6）。`[R8]`

## 4. 边界条件

### 4.1 尾斜杠：307 重定向

实测（注册路径带尾斜杠）：

```text
TRAIL /a    -> 307 loc=http://testserver/a/
TRAIL /a/   -> 200
```

| 注册 | 请求 | 结果 |
| --- | --- | --- |
| `/a/` | `/a` | 307 → `/a/` |
| `/a/` | `/a/` | 200 |
| `/a` | `/a/` | 307 → `/a` |

| 风险 | 说明 |
| --- | --- |
| 307 保留方法但不是所有客户端都跟随 | `POST` 可能失败 |
| 网关/CDN 对 307 处理不统一 | 线上偶发 404 |
| 关闭重定向 | `FastAPI(redirect_slashes=False)` → 直接 404 |

### 4.2 HEAD 不会自动支持

实测：

```text
HEAD /only-get -> 405  allow=GET
HEAD /items     -> 405
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `@app.get` 只注册 GET | 不隐含 HEAD | 实测 |
| 但框架内置路由**都带 HEAD** | `/docs` 等是 `['GET','HEAD']` | 实测 |
| 需要 HEAD 就显式声明 | 见 4.6 | `[R2]` |

> 注意：这会造成「用 `/docs` 探活成功、用自己的 `/health` 探活失败」的诡异现象——因为前者是框架路由（支持 HEAD），后者是你写的（不支持）。

### 4.3 204 不能有响应体

实测两种写法：

```text
204+Response: 204 body='' cl=None
204+None    : 204 body='' cl=None
```

| 写法 | 结果 | 评价 |
| --- | --- | --- |
| `status_code=204` + `return Response(status_code=204)` | 204，空体 | ✅ 推荐 |
| `status_code=204` + `return None` | 204，空体 | ✅ 也可以 |
| `status_code=204` + `return {...}` | 响应体被丢弃 | ⚠️ 依赖实现，别依赖 |
| 不写 `status_code` + `return None` | **200 + `null`** | ❌ 见第 01 章 4.4 |

### 4.4 同一路径重复注册

实测：

```text
DUP /same -> {'which': 'first'}
DUP routes: [..., ('/same', 'same_first'), ('/same', 'same_second')]
```

| 结论 | 说明 |
| --- | --- |
| **先注册的生效** | 匹配到第一个就返回 |
| 后注册的**仍在路由表里** | 永远不会命中，但会出现在 `app.routes` |
| 文档里会出现两条 | 前端困惑 |

> 注意：这类重复常见于「复制粘贴新增接口忘了改路径」。自查命令：`[r.path for r in app.routes]` 看有没有重复。

### 4.5 `:path` 转换器必须放最后

```text
PATH /files/a/b/c.txt     -> 200 {'path': 'a/b/c.txt'}
PATH /files/x             -> 200 {'path': 'x'}
```

| 事实 | 说明 |
| --- | --- |
| `.*` 会吞掉后面所有段 | 注册在它后面的路由基本不可达 |
| 适合静态文件、文件路径 | 不适合普通业务接口 |

### 4.6 多方法注册与 `Duplicate Operation ID`

用 `api_route(methods=["GET","HEAD"])` 时，实测出现：

```text
UserWarning: Duplicate Operation ID health_health_get for function health at .../main.py
```

| 原因 | 解决 |
| --- | --- |
| 两个方法共用同一函数，`operation_id` 按「函数名 + 方法」生成，HE... 相同 | 用两个装饰器，HEAD 那条设 `include_in_schema=False` |

```python
@app.get("/health", tags=["运维"])
@app.head("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
```

实测改为双装饰器后（`python -W error::UserWarning verify.py`）：无警告，`HEAD /health` 仍返回 200。

### 4.7 `include_in_schema=False` 不是权限

```text
HIDDEN status: 200
HIDDEN in openapi: False
```

| 结论 | 说明 |
| --- | --- |
| 路由**照常可用** | 只是不出现在 `/docs` 与 `/openapi.json` |
| 不是安全措施 | 知道路径就能调 |
| 真正保护 | 依赖鉴权（第 46 章） |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 通配路由写在精确路由前 | 实测精确路径被吃掉，返回 200 但数据错 | 精确在前 | 实测 |
| 依赖 `app.routes` 的顺序不变 | 加入新 router 后顺序变化 | 显式排序 | `[R3]` |
| 认为 422 是「参数没传」 | 实际是「传了但不合法」 | 看 `loc` 字段 | `[R2]` |
| `GET /items/abc` 期望 404 | 实测 422 | 用 `{id:int}` 或前端保证 | 实测 |
| `@app.get` 期望支持 HEAD | 实测 405 | 双装饰器 | 实测 |
| `api_route` 多方法 | `Duplicate Operation ID` 警告 | 拆成多个装饰器 | 实测 |
| 204 返回 JSON | 响应体被丢弃 | 返回 `Response(204)` | 实测 |
| 不写 `status_code` 就期望 201 | 默认 200 | 显式 `status.HTTP_201_CREATED` | `[R2]` |
| 用 GET 做写操作 | 被缓存/预取/爬虫误触发 | POST/PUT/PATCH/DELETE | `[R4]` |
| DELETE 返回 200 + 内容 | 语义不清 | 204 | `[R4]` |
| 用 200 表示业务失败 | 监控失真 | 4xx + 业务码 | `[R4]` |
| `path` 不带前导 `/` | 启动报错 | `"/items"` | `[R2]` |
| 同一路径重复注册 | 后者永不命中 | 自查 `routes` | 实测 |
| `name` 重复 | `url_path_for` 命中错的那个 | name 唯一 | `[R8]` |
| 硬编码路径拼 URL | 改前缀全崩 | `url_path_for` | `[R1]` |
| `:path` 放在前面 | 后面路由全不可达 | 放最后 | `[R3]` |
| 用 `include_in_schema=False` 做权限 | 接口照样能访问 | 鉴权依赖 | 实测 |
| 认为 405 是路径错 | 405 说明路径对、方法错 | 看 `Allow` | `[R3]` |
| 依赖 `Allow` 头枚举全部方法 | 实测只给第一个 | 查 `routes` 表 | 实测 |
| 尾斜杠混用 | 307 跳转，POST 可能失败 | 统一不带尾斜杠 | 实测 |
| 关掉 `redirect_slashes` 却没改前端 | 404 增多 | 两侧同步 | `[R3]` |
| 路径里用大写 | 大小写敏感，前端易错 | 全小写 + 连字符 | `[R5]` |
| 路径用动词（`/getItems`） | 不符合 REST | `/items` + 方法 | `[R5]` |
| 路径里带 `.json` 后缀 | 与内容协商冲突 | 用 `Accept` 头 | `[R5]` |
| ID 用自增整数暴露业务量 | 泄露规模 | UUID/短码 | 第 17 章 |
| `PUT` 做部分更新 | 语义错、字段被清空 | `PATCH` | `[R4]` |
| `PATCH` 用 PUT 的语义 | 前端漏字段导致数据丢失 | 区分二者 | `[R4]` |
| 删除用软删但返回 204 | 前端以为物理删除 | 明确语义 | `[R4]` |
| 404 与 403 混用 | 泄露资源是否存在 | 无权限返回 403 或统一 404 | `[R6]` |
| 路由函数用 `async def` 但内部阻塞 | 事件循环被占 | 见第 01 章 2.2 | `[R1]` |
| 在装饰器里写业务逻辑 | 难以复用与测试 | 装饰器只做注册 | `[R7]` |
| 一个函数挂太多路由 | 行为差异难维护 | 一函数一路由 | `[R7]` |
| `deprecated=True` 却不给替代方案 | 前端不知道怎么迁 | `description` 写迁移指引 | `[R2]` |
| 忽略 `operation_id` | 生成的客户端函数名丑陋 | 显式指定 | `[R8]` |
| 用 `@app.get("/")` 当健康检查 | 与首页冲突 | 独立 `/health` | `[R4]` |
| 大量路由写在 `main.py` | 文件膨胀 | 拆 `APIRouter` | 第 04、65 章 |

## 6. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 精确路径写在通配路径之前 | 唯一可靠的做法 | 实测 |
| 用 `{id:int}` 而非仅标注 `int` | 404 更准确 | `[R3]` |
| 路径全小写、复数名词、连字符 | `/user-orders` 而非 `/getUserOrders` | `[R5]` |
| 状态码语义化 | 201/204/400/404/409/422 | `[R4]` |
| 一个资源一组路由 | 便于拆 router | 第 65 章 |
| `name` 显式命名 | 反向解析稳定 | `[R1]` |
| `summary` 写人话 | 文档可读性 | `[R2]` |
| 健康检查单独文件 | 与业务解耦 | `[R4]` |
| 用 `url_path_for` 生成内部链接 | 避免硬编码 | `[R1]` |
| 自定义路由集中放 | 避免顺序混乱 | `[R3]` |

**风格示范**：

```python
"""items.py：一个资源一组路由，顺序遵循「精确 → 通配」。"""

from fastapi import APIRouter, Response, status

router = APIRouter(prefix="/items", tags=["商品"])


@router.get("/latest", summary="最新商品")          # 精确，必须在前
def get_latest() -> dict[str, str]: ...


@router.get("", summary="商品列表")
def list_items() -> list[dict[str, object]]: ...


@router.get("/{item_id:int}", summary="商品详情")    # 通配，必须在后
def get_item(item_id: int) -> dict[str, object]: ...


@router.delete("/{item_id:int}", status_code=status.HTTP_204_NO_CONTENT, summary="删除商品")
def delete_item(item_id: int) -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

**自查命令**：

```powershell
# 列出所有路由（排查重复与顺序）
uv run python -c "import main; [print(r.path, sorted(getattr(r,'methods',[]) or [])) for r in main.app.routes]"
```

**边界**：

- 本章的 `DB` 是模块级字典，多进程下不共享（第 02 章 2.5）。
- 路由顺序问题在 `include_router` 时同样存在：**先 include 的 router 优先级更高**，第 04、65 章展开。
- 本章没有请求体，POST/PUT/PATCH 用查询参数接收数据，仅为聚焦路由；真实写法见第 13 章。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[R1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/first-steps/ | `APIRouter`/`app` 路由注册、`url_path_for` |
| `[R2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/path-operation-configuration/ | 路由参数、`status_code`、`tags`、`deprecated` |
| `[R3]` | 官方文档 | https://www.starlette.io/routing/ | 路由匹配算法、`Match.FULL/PARTIAL`、转换器、`redirect_slashes` |
| `[R4]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110 | HTTP 方法语义、幂等性、状态码 |
| `[R5]` | 规范 | https://restfulapi.net/resource-naming/ | 资源命名约定 |
| `[R6]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#section-15.5.4 | 403 与 404 的安全取舍 |
| `[R7]` | 官方文档 | https://peps.python.org/pep-0008/ | 命名与可读性 |
| `[R8]` | 规范 | https://spec.openapis.org/oas/latest.html | `operationId` 唯一性 |

> **核对状态**：`[R4]`–`[R6]`、`[R8]` 为规范/约定类来源；`[R1]`–`[R3]`、`[R7]` 按官方文档结构整理，**本次未逐页直连复核**。文中「实测」为本机真实输出，`examples/verify.py` 可复现 11/11 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 路由三元组是什么，存在哪里
- [ ] 匹配算法的四步
- [ ] 为什么精确路径会被通配吃掉
- [ ] 404 / 405 / 422 的触发条件
- [ ] `{id:int}` 与标注 `int` 的差别
- [ ] 204 为什么不能有响应体

**能写出（代码层）**：

- [ ] 一个资源的完整 CRUD（含正确状态码）
- [ ] 精确路径 + 通配路径的正确顺序
- [ ] GET+HEAD 双装饰器写法
- [ ] `:path` 转换器路由
- [ ] `include_in_schema=False` 的内部接口
- [ ] 用 `url_path_for` 生成地址

**能判断（避坑层）**：

- [ ] 看到 `/latest` 拿不到能立刻想到注册顺序
- [ ] 看到 405 能知道路径对、方法错
- [ ] 看到 `HEAD` 405 能指出 `@app.get` 不含 HEAD
- [ ] 看到 `api_route` 多方法能预判 operation_id 警告
- [ ] 看到重复路径能指出后者永不命中
- [ ] 看到 `include_in_schema=False` 能指出它不是权限

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 11/11
- [ ] 调整注册顺序复现「latest 被吃掉」
- [ ] `python -W error::UserWarning verify.py` 无警告

## 9. 下一章衔接

第 04 章 `项目骨架`：把本章的单个 `main.py` 拆成 `app/main.py + app/api/v1/router.py + app/core/config.py`，讲清 `include_router` 的 `prefix`/`tags` 叠加规则、包内相对导入、循环导入的三种解法。

本章留下的伏笔：

1. `url_path_for` 在带前缀 router 下的行为——第 04 章实测。
2. 路由顺序在 `include_router` 时依然生效——第 04、65 章。
3. 状态码语义化之后，错误响应结构怎么统一——第 31、34 章。
