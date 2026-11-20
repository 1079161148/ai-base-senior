# 48 作用域授权（SecurityScopes）

## 一句话结论

端点用 `Security(get_current_user, scopes=["items:write"])` 声明需要什么；框架把所有依赖声明的 scope **汇总**成 `SecurityScopes` 注入你的函数，你比对 token 里的 scopes 是否覆盖。不够就返 **403**，且 `WWW-Authenticate` 必须写 `Bearer scope="items:write" error="insufficient_scope"`——这是客户端知道「该申请什么权限」的唯一途径。

四个实测要点：

1. **多个 scope 是 AND**：`scopes=["items:read","items:write"]` → OpenAPI 里写成同一个对象 `{"OAuth2PasswordBearer": ["items:read","items:write"]}`，两个都必须有。
2. 多 scope 的 challenge 是空格连接：`scope="items:read items:write"`（`SecurityScopes.scope_str`）。
3. **无 token 先 401，scope 不够才 403**——顺序不能反（实测无 token 时 `WWW-Authenticate` 是纯 `Bearer`）。
4. 发 token 时只授予「用户拥有 ∩ 客户端请求」：alice 请求 3 个 scope 只拿到 `["items:read"]`。

## 最小可运行案例

```python
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import OAuth2PasswordBearer, SecurityScopes

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={"items:read": "读取商品", "items:write": "修改商品"},
)

USERS = {"alice": {"scopes": ["items:read"]}, "admin": {"scopes": ["items:read", "items:write"]}}


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    security_scopes: SecurityScopes,
) -> dict[str, Any]:
    payload = decode(token)                     # 第 47 章
    user = USERS.get(payload["sub"])
    if user is None:
        raise HTTPException(401, "用户不存在")
    for scope in security_scopes.scopes:
        if scope not in payload.get("scopes", []):
            raise HTTPException(
                403,
                f"缺少 scope: {scope}",
                headers={
                    "WWW-Authenticate": f'Bearer scope="{security_scopes.scope_str}" error="insufficient_scope"'
                },
            )
    return user


@app.get("/items")
async def read_items(
    user: Annotated[dict[str, Any], Security(get_current_user, scopes=["items:read"])],
) -> dict:
    return {"items": [], "user": user}
```

完整版本（多 scope、交集授予、装饰器位置）见 `examples/main.py`。

## 怎么跑

```powershell
cd "07-安全认证\48-作用域授权\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] flows scopes -> scopes=['admin', 'items:read', 'items:write']
[PASS] 路由 security 带 scopes -> GET=read, POST=write, DELETE=read+write
[PASS] 装饰器位置 -> 装饰器位置也可带 scopes
[PASS] 授予取交集 -> alice 请求 3 个 → 只授予 ['items:read']
[PASS] 空 scope 用户 -> bob scopes=[]，访问 /items → 403
[PASS] 有 read 放行 -> 200 alice
[PASS] 缺 write 403 -> Bearer scope="items:write" error="insufficient_scope"
[PASS] 多 scope 是 AND -> 只有 read → 403；read+write → 200
[PASS] admin scope -> alice→403, admin→200
[PASS] 无 token 401 -> 401 在 scope 校验之前
[PASS] token 带 scopes -> scopes=['admin', 'items:write']
[PASS] scope_str 空格连接 -> scope_str 以空格连接

结果：12/12 通过
```

## 核心 API 速查

| 位置 | 写法 | 作用 |
| --- | --- | --- |
| 方案 | `OAuth2PasswordBearer(scopes={...})` | 写 `flows.password.scopes` 字典 |
| 端点参数 | `Security(get_current_user, scopes=["x"])` | 声明所需 scope |
| 依赖参数 | `security_scopes: SecurityScopes` | 拿到汇总后的 scopes |
| 装饰器 | `dependencies=[Security(fn, scopes=["x"])]` | 只校验不取值 |

| `SecurityScopes` 属性 | 内容 |
| --- | --- |
| `.scopes` | 本请求所有依赖声明合并后的列表 |
| `.scope_str` | 空格连接的字符串（用于 challenge）|

| 实测行为 | 结果 |
| --- | --- |
| `/items` GET/POST/DELETE | 分别 `["items:read"]` / `["items:write"]` / 两者 |
| 授予 | 交集（3 个请求 → 1 个授予）|
| 空 scope 用户 | `scopes=[]`，访问 → 403 |
| 缺 scope | 403 + `scope="..." error="insufficient_scope"` |
| 多 scope challenge | `scope="items:read items:write"` |
| 无 token | 401（先于 403）|

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 把客户端请求的 scope 全授予 | 越权 | 取交集 |
| 403 不带 `scope=`/`insufficient_scope` | 客户端不知申请什么 | 完整 challenge |
| 用 `=` 拼多 scope | 客户端解析错 | 空格连接 |
| 缺 token 返回 403 | 语义错 | 401 |
| scope 校验写在路由里 | 每个端点重复 | 写在依赖 |
| 只用 `Depends` 不用 `Security` | OpenAPI 缺 scopes | `Security(..., scopes=...)` |
| 以为多 scope 是 OR | 只有一个也能进 | 是 AND |
| token 里不写 scopes | 依赖读不到 | 签发时带上 |
| scope 命名随意（`read`）| 冲突 | 用 `资源:动作` |
| 把 scope 当角色用 | 组合爆炸 | scope 控能力、角色控人 |

## 毕业自查

- [ ] 能写出带 scopes 的 `Security`
- [ ] 能解释 `SecurityScopes` 的汇总行为
- [ ] 能写出正确的 403 challenge
- [ ] 能说明「交集授予」为什么必须
- [ ] 能区分 401（没认证）与 403（权限不够）
- [ ] 动手题一：给 `/admin` 加 `admin` scope 并写越权用例
- [ ] 动手题二：把 scope 映射到数据库里的角色表

> 想看 `SecurityScopes` 的构造过程、scope 设计规范（RFC 6749 §3.3）、与角色模型的取舍、18 条坑，继续读 [`base.md`](./base.md)。