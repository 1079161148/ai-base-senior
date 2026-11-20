# 22 状态码 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「状态码在 FastAPI 里怎么被决定、谁覆盖谁、哪些码不能有 body、错误码怎么设计」拆开。学完这章，你要能给每个端点一眼选对状态码。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测） |
| 前置 | 第 21 章（响应模型） |
| 覆盖范围 | `status_code` 三种设置方式、204/1xx/304 的 body 限制、OpenAPI 影响、错误码设计 |
| 明确不覆盖 | 异常处理器（第 33 章）、响应头细节（第 24 章）、限流（第 51 章） |
| 学完验收 | 能跑通 `verify.py` 11/11、能预测三种改码方式的最终值、能避开 204 的 body 陷阱 |

## 0. 怎么用这份文件

**依据约定**：`` `[Sn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 200 只是默认值
2 机制（第 2 节）    → 三种改码谁覆盖谁
3 API（第 3 节）     → status_code / Response / HTTPException
4 边界（第 4 节）    → 204、1xx、304、自定义码、OpenAPI
5 注意事项（第 5 节）→ 20 条对照
6 最佳实践（第 6 节）→ 状态码选择表
```

## 1. 概念：200 不是「正确」，只是「没写」

| 语义 | 码 | 客户端典型处理 |
| --- | --- | --- |
| 查询成功 | 200 | 直接读 body |
| 创建成功 | 201 | 读 `Location` 拿新资源地址 |
| 受理（异步）| 202 | 轮询任务状态 |
| 删除成功 | 204 | 不读 body |
| 条件请求未变 | 304 | 用缓存 |
| 参数错 | 422 | 展示字段错误 |
| 未认证 | 401 | 跳登录 |
| 无权限 | 403 | 提示无权限 |
| 不存在 | 404 | 提示「没有」或新建 |
| 冲突 | 409 | 提示重复/重试 |
| 限流 | 429 | 退避重试 |

「一律 200 + body 里放 code」的做法会让网关、监控、SDK 全部失灵：它们只看状态码。

## 2. 机制：三种改码方式的覆盖关系

```text
装饰器 status_code=201          ← 默认值，写进 OpenAPI
   ↓ 被覆盖
response: Response 注入         ← 函数内改，运行时生效
   ↓ 被覆盖
raise HTTPException(status)     ← 直接终止，返回该状态码
```

| 组合 | 实际状态码（实测） |
| --- | --- |
| 装饰器 201 | 201 |
| 装饰器 201 + `response.status_code=202` | 202 |
| 装饰器 200 + `raise HTTPException(404)` | 404 |
| 装饰器 201 + 函数内改 202 + 抛 404 | 404 |

`HTTPException` 走异常处理器，完全不经过响应模型的序列化。

## 3. API 逐个拆解

### 3.1 `status_code=`

```python
from fastapi import status

@app.post("/items", status_code=status.HTTP_201_CREATED)
```

| 要点 | 说明 |
| --- | --- |
| 接受 int 常量 | `status.HTTP_201_CREATED` == 201 |
| 会写进 OpenAPI | `responses` 从 `200` 变成 `201` |
| 只影响默认成功响应 | 异常分支仍然按异常自己的码 |
| 影响响应模型校验 | 204 时禁止 body（见 4.1） |

### 3.2 注入 `Response`

```python
@app.post("/items/async", status_code=201)
def create(item: ItemIn, response: Response) -> ItemOut:
    response.status_code = status.HTTP_202_ACCEPTED
    return ItemOut(id=0, name=item.name)
```

| 要点 | 说明 |
| --- | --- |
| `Response` 不是返回值 | 它只是「可写的响应对象」 |
| 还能加头/改媒体类型 | `response.headers["X-Id"] = "1"` |
| OpenAPI 看到的仍是装饰器的码 | 运行时与文档不一致，慎用 |

### 3.3 `HTTPException`

```python
raise HTTPException(status_code=404, detail="商品不存在")
```

| 要点 | 说明 |
| --- | --- |
| 覆盖装饰器状态码 | 实测 |
| body 固定为 `{"detail": ...}` | 想换结构用自定义异常处理器（第 33 章） |
| 不经过响应模型 | 不会触发 500 |

## 4. 边界条件

### 4.1 204 与 body：定义期就报错（实测）

```python
@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int) -> dict[str, int]:   # ← 返回注解是 dict
    return {"deleted": item_id}
```

导入模块时抛：

```text
AssertionError: Status code 204 must not have a response body
```

| 尝试 | 结果（实测） |
| --- | --- |
| `status_code=204` + `-> None` | ✅ 正常，body 空 |
| `status_code=204` + `-> dict` | ❌ 导入期 AssertionError |
| `status_code=204` + `response_model=X` | ❌ 同样报错 |
| `status_code=99`（1xx） | ❌ `Status code 99 must not have a response body` |

结论：204 端点只能声明「无返回体」。这不是运行时丢弃，而是框架帮你卡在定义期——比静默丢弃更好，但也意味着「先写 204 再改代码」会直接起不来。

### 4.2 304 与 1xx

| 码段 | body | 说明 |
| --- | --- | --- |
| 1xx | 禁止 | FastAPI 断言拦截 |
| 204 | 禁止 | 同上 |
| 304 | 禁止 | 条件请求，无 body |
| 2xx 其它 | 允许 | 正常 |
| 3xx（301/302）| 允许但通常不用 | 用 `RedirectResponse` |

### 4.3 201 与 `Location`

实测：装饰器 `status_code=201` **不会**自动加 `Location` 头。

```python
@app.post("/items", status_code=201)
def create(item: ItemIn, response: Response) -> ItemOut:
    created = ItemOut(id=1, name=item.name)
    response.headers["Location"] = f"/items/{created.id}"
    return created
```

REST 约定：201 应带 `Location`。要不要强制取决于团队，但客户端可能依赖。

### 4.4 自定义状态码

| 写法 | 结果（实测） |
| --- | --- |
| `status_code=299` | ✅ 正常返回 299 |
| `status_code=799` | 取决于 Starlette 校验（本章未实测） |
| OpenAPI 描述 | 299 会出现在 `responses` 里，无标准描述文案 |

不建议自定义业务码：网关/客户端常按标准码段处理。

### 4.5 OpenAPI 影响

| 端点 | `responses` 键（实测） |
| --- | --- |
| POST 201 | `['201', '422']` |
| DELETE 204 | `['204', '422']`，且 204 **无 content** |
| GET 200 | `['200', '422']` |

文档里的响应结构直接来自状态码 + 响应模型，SDK 生成器依赖它。

### 4.6 错误码设计

| 原则 | 说明 |
| --- | --- |
| 4xx 表示「客户端可修复」 | 参数、权限、冲突 |
| 5xx 表示「服务端问题」 | 别用来表达业务失败 |
| 422 与 400 | FastAPI 默认用 422 表达校验失败 |
| 同一语义固定一个码 | 不要一会儿 400 一会儿 422 |
| 业务错误用 `detail.code` 细分 | HTTP 码不够细时 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 204 端点写 `-> dict` | 导入期 AssertionError | 返回注解 `None` | 实测 |
| 以为 204 会静默丢 body | 根本起不来 | 同上 | 实测 |
| 用 1xx 做业务码 | 断言拦截 | 用 2xx/4xx | 实测 |
| 创建返回 200 | 语义丢失 | 201 | `[S1]` |
| 以为 201 自动加 Location | 实测没有 | 手动加头 | 实测 |
| 装饰器与函数内都改码 | 文档与运行不一致 | 只改一处 | 实测 |
| 业务失败返回 500 | 监控误报 | 4xx | `[S3]` |
| 删除成功返回 200 + body | 语义冗余 | 204，或 200 + 明确体 | `[S1]` |
| 用 200 表示「部分失败」 | 客户端不重试 | 207 或 4xx | `[S2]` |
| 422 与 400 混用 | 客户端分支混乱 | 统一约定 | `[S1]` |
| 用 403 表示「未登录」 | 客户端不跳登录 | 401 | `[S3]` |
| 用 404 掩盖 403 | 权限模型难排查 | 按安全策略明确 | `[S3]` |
| 异步任务返回 200 | 客户端不知道要轮询 | 202 + 任务 id | `[S2]` |
| 所有错误都 `detail="错误"` | 无法定位 | 结构化 detail | 第 33 章 |
| 主动抛 500 掩盖 bug | 监控失真 | 让异常冒泡 | `[S3]` |
| 304 带 body | 违规 | 只返回头 | `[S2]` |
| 头文件里 `status_code` 用字符串 | 类型错误 | 用 int/常量 | `[S1]` |
| 认为状态码能替代鉴权 | 只影响表述 | 权限在依赖层 | 第 44 章 |
| 204 端点里做重计算 | 白算 | 移到后台任务 | `[S4]` |
| OpenAPI 未同步 | SDK 生成错误 | 保证装饰器码真实 | 实测 |
| 204 端点又写了 `response_model=` | 定义期报错 | 删掉该参数 | 实测 |

## 6. 最佳实践与编码建议

### 6.1 状态码选择表（可直接抄）

| 端点 | 成功码 |
| --- | --- |
| `GET /items` | 200 |
| `GET /items/{id}` | 200 / 404 |
| `POST /items` | 201 + `Location` |
| `PUT /items/{id}` | 200（替换后返回）或 204 |
| `PATCH /items/{id}` | 200 |
| `DELETE /items/{id}` | 204 |
| `POST /jobs` | 202 + 任务 id |
| 条件 GET | 200 / 304 |

### 6.2 模板

```python
from fastapi import FastAPI, Response, status

app = FastAPI()


@app.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(item: ItemIn, response: Response) -> ItemOut:
    created = save(item)
    response.headers["Location"] = f"/items/{created.id}"
    return created


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int) -> None:
    if not exists(item_id):
        raise HTTPException(status_code=404, detail="不存在")
    remove(item_id)
```

### 6.3 编码建议

| 建议 | 说明 |
| --- | --- |
| 用 `status.HTTP_*` 常量 | 比裸数字可读 |
| 一个端点只在一处设定码 | 避免文档漂移 |
| 204 端点返回 `None` | 别写返回体 |
| 创建配 `Location` | REST 约定 |
| 错误码集中定义 | 团队统一 |
| OpenAPI 里补 4xx 描述 | `responses={404: {...}}`（第 26 章） |
| 别自造业务码段 | 用 detail.code |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[S1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/response-status-code/ | `status_code` 用法与常量 |
| `[S2]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#section-15 | 各状态码语义与 body 规则 |
| `[S3]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#section-15.5 | 4xx/5xx 分工 |
| `[S4]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/background-tasks/ | 后台任务与 202 |

> **核对状态**：`[S1]`–`[S4]` 为官方文档/规范链接，**本次未逐页直连复核**；204/1xx 的 body 断言、201 无 Location、Response 覆盖顺序、OpenAPI 结构均为本机实测，`examples/verify.py` 复现 11/11 通过。4.4 中 799 等超范围码**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 三种改码方式的覆盖顺序
- [ ] 204 为什么禁止 body
- [ ] 1xx/304 的 body 规则
- [ ] 201 与 Location 的关系
- [ ] 422 与 400 的选择
- [ ] 4xx 与 5xx 的分工

**能写出（代码层）**：

- [ ] 201 创建端点
- [ ] 204 删除端点
- [ ] `Response` 注入改码
- [ ] `HTTPException` 覆盖
- [ ] `Location` 头

**能判断（避坑层）**：

- [ ] 看到 204 带返回体 → 指出定义期报错
- [ ] 看到全 200 → 指出语义与监控问题
- [ ] 看到业务错误抛 500 → 指出监控失真
- [ ] 看到 403 当未登录 → 指出应用 401
- [ ] 看到装饰器与运行时不一致 → 指出文档漂移

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 11/11
- [ ] `/docs` 里 POST 显示 201、DELETE 显示 204
- [ ] 手工用 `curl -i` 看状态行

## 9. 下一章衔接

第 23 章 `联合类型响应`：一个端点可能返回「成功」或「错误」两种结构，或 `Response` 与模型二选一。下一章讲 `Union` 响应、`response_model` 与 `responses=` 的组合，以及 OpenAPI 里的 `anyOf`。

本章留下的伏笔：

1. `Location` 头属于响应头，第 24 章系统讲。
2. 错误响应结构统一在第 33 章。
3. `responses={...}` 自定义文档在第 26 章。
4. 202 + 后台任务在 M08/M10。
