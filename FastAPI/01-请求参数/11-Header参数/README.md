# 11 Header 参数

## 一句话结论

`Header()` 读请求头。默认 `convert_underscores=True`：函数参数写 `user_agent` 自动对应 `User-Agent`（下划线↔连字符互转）。头名**大小写不敏感**，重复头会解析成 `list[str]`，必填头缺失的 `loc` 用的是**连字符形式**。

学完这一章，你能：正确读自定义头与标准头、说清 `convert_underscores=False` 的双向陷阱、用 Header 实现幂等键与追踪 id。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import FastAPI, Header

app = FastAPI()


@app.get("/me")
def me(
    # 【作用】convert_underscores=True（默认）→ 自动对应 User-Agent
    user_agent: Annotated[str | None, Header()] = None,
    # 【作用】x_token → X-Token
    x_token: Annotated[str | None, Header()] = None,
) -> dict[str, str | None]:
    return {"user_agent": user_agent, "x_token": x_token}
```

完整版本（多值头、必填头、幂等键）见 `examples/main.py`。

## 怎么跑

```powershell
cd "01-请求参数\11-Header参数\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 标准头自动对应 -> pytest/1.0
[PASS] 头名大小写不敏感 -> lower/1.0
[PASS] 自定义头 -> tk
[PASS] 重复头解析为列表 -> ['a', 'b']
[PASS] 必填头缺失 422 -> loc=['header', 'x-api-key']
[PASS] convert_underscores=False 只认下划线 -> 200 / None
[PASS] 缺失时为 None -> x_token=None, accept_language=None, user_agent=testclient（客户端默认）
[PASS] OpenAPI in=header -> user-agent required=false
[PASS] 幂等键走头 -> 第二次返回 cached

结果：9/9 通过
```

## 核心 API 速查

| 写法 | 对应请求头 |
| --- | --- |
| `user_agent: Annotated[str, Header()]` | `User-Agent` |
| `x_token: Annotated[str, Header()]` | `X-Token` |
| `x_tag: Annotated[list[str], Header()]` | `X-Tag`（可重复） |
| `Header(convert_underscores=False)` + `user_agent` | `user_agent`（下划线头） |
| `Header(alias="X-Custom")` + `custom: str` | `X-Custom` |
| `Header(default="x")` | 可选，缺省 `"x"` |

| 特性 | 行为 |
| --- | --- |
| 大小写 | **不敏感**（`user-agent` 与 `User-Agent` 等价） |
| 下划线转连字符 | 默认开（`convert_underscores=True`） |
| 重复头 | `list[str]` 收集全部 |
| 必填缺失 | 422 `missing`，`loc: ["header", "x-api-key"]` |
| 空值头 | 得到 `""`（不是 `None`） |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `Header(convert_underscores=False)` 后用标准头名 | 实测**读不到**（只认 `user_agent` 这种下划线头） | 要么保持默认 `True`，要么用 `alias` |
| 以为头名大小写敏感 | 实际不敏感 | 放心用 |
| 用 `list[str]` 读单值头 | 得到 `["v"]`，需取 `[0]` | 单值就用 `str` |
| 必填头用 `Header()` 无默认值 | 缺失 422，前端体验差 | 可选 + 业务层 401 |
| 用 Header 传大 JSON | 头有大小限制（通常 8KB） | 用 body |
| 自定义头不加 `X-` 前缀 | 可能与标准头冲突 | 用 `X-` 或 `Trace-` 前缀 |
| 在 `loc` 里按函数参数名找 | 实际是 kebab-case | 按 `x-api-key` 定位 |
| 信任 `X-Forwarded-For` 不限来源 | 可伪造 IP | 配 `--forwarded-allow-ips` |
| 用 Header 传中文不编码 | 头只允许 ASCII（latin-1） | URL 编码或 Base64 |

## 毕业自查

- [ ] 能说出 `convert_underscores` 的作用与默认值
- [ ] 能说出 `False` 时会发生什么（实测：只认下划线头）
- [ ] 能写出读 `User-Agent` 与自定义头的代码
- [ ] 能说出头名大小写规则
- [ ] 能说出必填头缺失的 `loc` 长什么样
- [ ] 能用 Header 实现幂等键
- [ ] 动手题一：读 `Accept-Language`，不传时返回 `en`
- [ ] 动手题二：写一个 `Idempotency-Key` 去重接口

> 想看 `loc` 命名的原因、多值头、代理头安全、22 条坑，继续读 [`base.md`](./base.md)。
