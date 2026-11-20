# 31 HTTPException

## 一句话结论

业务上「可预期」的失败用 `raise HTTPException(status_code, detail, headers)`，框架统一转成 `{"detail": ...}`。`detail` 可以是 dict/list；`headers` 用来带 `WWW-Authenticate`（401 必备）、`Retry-After`（429）。**不可预期**的异常不要自己包成 500——交给兜底处理器。`HTTPException` 只在请求-响应阶段有效，后台任务里抛**不会**产生 404（实测：响应已是 200）。

学完这一章，你能：区分 400/401/403/404/409/429、把 `detail` 设计成可解析结构、在依赖里统一抛错、避开「头值写中文 500」。

## 最小可运行案例

```python
from fastapi import FastAPI, HTTPException, status

app = FastAPI()

_ITEMS = {1: {"id": 1, "name": "机械键盘"}}


@app.get("/items/{item_id}")
def get_item(item_id: int) -> dict:
    item = _ITEMS.get(item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"item {item_id} 不存在",
        )
    return item


@app.get("/me")
def read_me(authorization: str | None = None) -> dict:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少凭据",
            headers={"WWW-Authenticate": "Bearer"},   # 401 的协议要求
        )
    return {"user": "alice"}
```

完整版本（结构化 detail、409、429、依赖抛错、后台任务反例、中文头 500）见 `examples/main.py`。

## 怎么跑

```powershell
cd "05-错误处理\31-HTTPException\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 404 字符串 detail -> 404 detail=item 99 不存在
[PASS] 200 正常 -> 200 机械键盘
[PASS] 结构化 detail -> 结构化 detail keys=['hint', 'item_id', 'reason']
[PASS] 401 + WWW-Authenticate -> www-authenticate=Bearer
[PASS] 401 无效凭据 -> Bearer error="invalid_token"
[PASS] 200 有效凭据 -> user=alice
[PASS] 409 冲突 -> 名称已存在: 机械键盘
[PASS] 429 + Retry-After -> 第 3 次起 429 + retry-after=30
[PASS] 依赖里抛 401 -> 缺 token → 401；有 token → 200
[PASS] 未捕获异常 500 -> 500 body='Internal Server Error'
[PASS] 后台任务异常 -> 状态码 200（响应已发出，404 不生效）
[PASS] 不存在的路由 -> 默认 detail=Not Found
[PASS] 405 方法不允许 -> 405 allow=GET
[PASS] OpenAPI 不含 404 -> responses=['200', '422']
[PASS] 头值中文 500 -> 头值含中文 → 500（latin-1 编码失败）
[PASS] Starlette 子类 -> isinstance(starlette.HTTPException) = True

结果：16/16 通过
```

## 核心 API 速查

```python
HTTPException(status_code=404, detail="...", headers={"X-Why": "..."})
```

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `status_code` | `int` | 必填，建议用 `status.HTTP_*` 常量 |
| `detail` | `Any` | 默认处理器原样放进 `{"detail": ...}` |
| `headers` | `dict[str, str]` | 附加响应头，值必须 latin-1 可编码 |

| 状态码 | 语义 | 必备头 / 注意 |
| --- | --- | --- |
| 400 | 请求本身有问题 | 校验失败优先用 422（框架默认）|
| 401 | 没认证 / 认证无效 | **必须** `WWW-Authenticate` |
| 403 | 认证了但没权限 | 不要用 401 代替 |
| 404 | 资源不存在 | 别用它掩盖 403（会泄露存在性）|
| 405 | 方法不允许 | 框架自动带 `Allow` |
| 409 | 与当前状态冲突 | 重复创建、乐观锁 |
| 422 | 结构/类型校验失败 | 框架自动产生（第 33 章定制）|
| 429 | 限流 | 建议 `Retry-After` |
| 500 | 服务端 bug | **不要**手动抛，交给兜底 |

| 实测行为 | 结果 |
| --- | --- |
| 未捕获异常 | 500，body 只有 `Internal Server Error`，不含堆栈 |
| 后台任务里抛 `HTTPException` | 响应已是 200，404 不生效 |
| 不存在的路由 | 404 `{"detail": "Not Found"}` |
| 方法不允许 | 405 + `Allow: GET` |
| OpenAPI | 只列 `200`/`422`，不会自动加 404 |
| 头值含中文 | 500（latin-1 编码失败）|

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 401 不带 `WWW-Authenticate` | 客户端不知道该用哪种认证 | 加 `headers={"WWW-Authenticate": "Bearer"}` |
| `headers` 值写中文 | 500，无提示 | 用英文或 RFC 5987 编码 |
| 捕获所有异常包成 500 | 泄露内部信息、丢 trace | 交给兜底处理器（第 34 章）|
| 在后台任务里抛 `HTTPException` | 不生效，响应已发出 | 记日志/落库告警 |
| 用 404 掩盖 403 | 安全上合理但要一致 | 明确策略并全站统一 |
| `detail` 拼内部路径/SQL | 信息泄露 | 只给用户可操作的信息 |
| 用 `detail` 传不可 JSON 化对象 | 序列化失败 → 500 | 先 `jsonable_encoder`（第 30 章）|
| 403 用 401 返回 | 客户端反复重试登录 | 已认证但无权限用 403 |
| 重复创建返回 400 | 语义不清 | 用 409 |
| 限流不返回 `Retry-After` | 客户端立刻重试 | 加该头 |
| 在依赖里 `return` 错误 dict | 路由照常执行 | 必须 `raise` |
| 认为 OpenAPI 会自动写 404 | 文档缺错误契约 | 手动 `responses={404: ...}`（第 26 章）|
| 把 `HTTPException` 当业务异常基类 | 状态码耦合进业务层 | 自定义异常 + 处理器（第 32 章）|

## 毕业自查

- [ ] 能说出 400/401/403/404/409/422/429 的边界
- [ ] 能写出带 `WWW-Authenticate` 的 401
- [ ] 能让 `detail` 变成可解析结构并说明契约成本
- [ ] 能在依赖里抛错并解释为什么不执行路由
- [ ] 能说出后台任务里 `HTTPException` 为什么无效
- [ ] 能解释「未捕获异常 → 500 且不泄露细节」
- [ ] 动手题一：给 `/items/{id}` 加 `responses={404: {"description": "不存在"}}`
- [ ] 动手题二：把 `/login` 的 429 改成「滑动窗口」并在头上返回剩余秒数

> 想看清 `HTTPException` 的默认处理器、`detail` 的序列化路径、状态码选择决策树、18 条坑，继续读 [`base.md`](./base.md)。