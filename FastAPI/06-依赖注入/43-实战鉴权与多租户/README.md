# 43 实战：鉴权与多租户

## 一句话结论

依赖链 `token → 主体 → 租户`，租户**只从 token 派生**。资源查询一律带 `tenant_id` 过滤；跨租户访问返回 **404**，与「不存在」同结构（实测 body 只有客户端已知的 id，不出现「属于别人」）。缺 token 401（带 `WWW-Authenticate`），token 错 401（`error="invalid_token"`），账号停用 403。`request.state` 在依赖里写入、端点里读取，实测一致。

学完这一章，你能：搭一条可复用的鉴权链、把租户隔离做在查询层、避开「用 403 泄露存在性」「信任客户端 X-Tenant」这类漏洞。

## 最小可运行案例

```python
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request

app = FastAPI()

TOKENS = {"tok-a": {"user": "alice", "tenant": "t-a", "active": True}}


def get_context(x_token: Annotated[str | None, Header(alias="X-Token")] = None) -> dict[str, Any]:
    if not x_token:
        raise HTTPException(401, "缺少 X-Token", headers={"WWW-Authenticate": "Bearer"})
    ctx = TOKENS.get(x_token)
    if ctx is None:
        raise HTTPException(401, "X-Token 无效")
    if not ctx["active"]:
        raise HTTPException(403, "账号已停用")
    return ctx


def tenant_context(
    request: Request,
    ctx: Annotated[dict[str, Any], Depends(get_context)],
) -> dict[str, Any]:
    request.state.tenant_id = ctx["tenant"]    # 只用 token 的租户
    return ctx


@app.get("/items/{item_id}")
def get_item(item_id: int, ctx: Annotated[dict[str, Any], Depends(tenant_context)]) -> dict:
    item = _ITEMS.get(item_id)
    if item is None or item["tenant"] != ctx["tenant"]:
        raise HTTPException(404, f"商品 {item_id} 不存在")   # 不区分「不存在」与「不属于你」
    return item
```

完整版本（列表过滤、创建绑定租户、`request.state` 传递）见 `examples/main.py`。

## 怎么跑

```powershell
cd "06-依赖注入\43-实战鉴权与多租户\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 缺 token -> 401 + WWW-Authenticate
[PASS] 错误 token -> 401 invalid_token
[PASS] 停用租户 -> 403 已停用
[PASS] 列表隔离 -> alice=2 条, bob=1 条
[PASS] 自己的资源 -> 200 自己的商品
[PASS] 跨租户 404 -> 跨租户 404 与不存在结构一致
[PASS] 创建绑定租户 -> id=4 绑定 t-a
[PASS] 忽略客户端租户 -> X-Tenant: t-b 被忽略
[PASS] state 传递 -> state_tenant=t-a
[PASS] 角色注入 -> role=admin
[PASS] OpenAPI 参数 -> parameters=['X-Token']
[PASS] 404 不泄露 -> 文案与不存在一致

结果：12/12 通过
```

## 核心 API 速查

| 依赖 | 作用 | 失败 |
| --- | --- | --- |
| `get_context` | token → 主体 + 租户 | 401 / 403 |
| `tenant_context` | 写 `request.state`，向下传递 | 继承上游 |
| `_find_item` | 带租户过滤的查询 | 404 |

| 状态码 | 场景 | 关键点 |
| --- | --- | --- |
| 401 | 没带 token / token 无效 | 必须 `WWW-Authenticate` |
| 403 | 认证过但无权限/停用 | 别用它表示「资源不属于你」|
| 404 | 资源不存在 **或** 跨租户 | 两者同结构 |

| 实测行为 | 结果 |
| --- | --- |
| 列表 | alice 2 条（t-a）, bob 1 条（t-b）|
| 跨租户读 | 404，与不存在同结构 |
| 创建时传 `tenant` 字段 | 被模型丢弃，绑定 token 租户 |
| 请求头 `X-Tenant: t-b` | 被忽略，仍按 token |
| `request.state` | 依赖写、端点读，值一致 |
| OpenAPI | 只暴露 `X-Token` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 信客户端 `X-Tenant` | 越权 | 从 token 派生 |
| 跨租户返回 403 | 泄露资源存在性 | 统一 404 |
| 查询不带 `tenant_id` | 越权读 | 所有查询加过滤 |
| 用 `assert` 做安全校验 | 500 且可被 `-O` 禁用 | `raise HTTPException` |
| 只在前端隐藏 | 后端无防护 | 服务端过滤 |
| 404 文案写「不属于你的租户」 | 信息泄露 | 与不存在一致 |
| 停用账号返回 401 | 客户端反复重试 | 403 |
| token 存明文比对 | 泄露风险 | 哈希/签名（第 44 章）|
| 把租户放全局变量 | 并发串租户 | `request.state` |
| 列表 count 不过滤 | 数量泄露 | count 同样加条件 |

## 毕业自查

- [ ] 能画出 `token → user → tenant` 依赖链
- [ ] 能说出 401/403/404 的选择
- [ ] 能解释为什么跨租户用 404
- [ ] 能把租户写进 `request.state`
- [ ] 能保证创建时绑定的是 token 租户
- [ ] 动手题一：加「租户管理员才能删」的角色校验
- [ ] 动手题二：把静态 token 换成 HMAC 签名并校验过期时间

> 想看租户隔离的查询层写法、`request.state` 与中间件的分工、越权测试用例、18 条坑，继续读 [`base.md`](./base.md)。