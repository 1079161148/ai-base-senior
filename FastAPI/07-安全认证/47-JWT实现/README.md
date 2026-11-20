# 47 JWT 实现（手写 HS256）

## 一句话结论

JWT = `base64url(header).base64url(payload).base64url(HMAC-SHA256(secret, header.payload))`，三段用 `.` 连接、**无 `=` 填充**。payload 只是 base64，**谁都能读**——实测不验签就能解出 `{"sub":"alice","exp":…}`。它能防的只有篡改：改 `sub` 保留原签名 → 401 `签名不符`；换密钥签 → 同样 401。

四个必须记住的点：

1. **必须校验 header 的 `alg`**。否则 `{"alg":"none"}` 的攻击 token 会被放行——实测我们拒绝了（`不支持的算法 'none'`）。
2. 对比签名用 `hmac.compare_digest`，不要用 `==`（防时序攻击）。
3. `exp` 是 **unix 秒**；过期 → 401 `已过期`，与签名错要区分开。
4. 密码用 **pbkdf2 + 随机 salt**，同密码两次哈希不同（实测），不要明文存。

## 最小可运行案例

```python
import base64, hashlib, hmac, json, time
from datetime import datetime, timedelta, timezone

SECRET = "change-me-in-production-32bytes-min"


def b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_token(sub: str, ttl_minutes: int = 30) -> str:
    now = datetime.now(timezone.utc)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
    }
    seg = f'{b64e(json.dumps(header, separators=(",", ":")).encode())}.{b64e(json.dumps(payload, separators=(",", ":")).encode())}'
    sig = hmac.new(SECRET.encode(), seg.encode(), hashlib.sha256).digest()
    return f"{seg}.{b64e(sig)}"


def decode_token(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("必须是三段")
    header = json.loads(b64d(parts[0]))
    if header.get("alg") != "HS256":          # 关键：拒绝 alg=none
        raise ValueError(f"算法 {header.get('alg')!r} 不支持")
    expected = b64e(hmac.new(SECRET.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, parts[2]):
        raise ValueError("签名不符")
    payload = json.loads(b64d(parts[1]))
    if payload["exp"] < time.time():
        raise ValueError("已过期")
    return payload
```

完整版本（FastAPI 端点、密码哈希、alg=none 攻击用例）见 `examples/main.py`。

## 怎么跑

```powershell
cd "07-安全认证\47-JWT实现\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] token 结构 -> segments=3, len=147
[PASS] header/claims -> header={'alg': 'HS256', 'typ': 'JWT'}, claims=['exp', 'iat', 'sub']
[PASS] payload 明文 -> payload 可直接 base64 解码
[PASS] 有效 token -> 200 alice
[PASS] 签名错 -> 401 签名不符
[PASS] 篡改 payload -> 改 sub 后签名不符
[PASS] alg=none -> 401 不支持的算法 'none'
[PASS] 过期 -> 401 已过期
[PASS] 格式错 -> 401 token 必须是三段
[PASS] 异密钥 -> 异密钥签名被拒
[PASS] challenge 头 -> Bearer error="invalid_token"
[PASS] 密码 salt -> salt 随机，校验通过
[PASS] 密码错 -> 400
[PASS] expires_in -> expires_in=1800

结果：14/14 通过
```

## 核心 API 速查

| 段 | 内容 | 编码 |
| --- | --- | --- |
| header | `{"alg":"HS256","typ":"JWT"}` | base64url，无填充 |
| payload | `sub`/`iat`/`exp`（+ 自定义） | base64url，无填充 |
| signature | `HMAC-SHA256(secret, header.payload)` | base64url，无填充 |

| 校验顺序 | 失败 |
| --- | --- |
| 段数 = 3 | `必须是三段` |
| `alg == HS256` | `不支持的算法`（防 none）|
| 签名一致（`compare_digest`）| `签名不符` |
| `exp >= now` | `已过期` |

| 实测行为 | 结果 |
| --- | --- |
| token 长度 | 147（30 分钟 TTL、单 claim）|
| `=` 填充 | 无 |
| 改 payload 保留签名 | 401 签名不符 |
| `alg: none` | 401 不支持的算法 |
| 异密钥 | 401 签名不符 |
| 同密码两次哈希 | 不同（salt 随机）|
| 响应字段 | `access_token`/`token_type`/`expires_in` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 不校验 `alg` | `none` 算法攻击 | 白名单校验 |
| 用 `==` 比签名 | 时序侧信道 | `compare_digest` |
| 以为 JWT 加密 | 敏感信息泄露 | 只放 `sub`/`scopes` |
| 把密码/手机号放 payload | 明文可见 | 放服务端 |
| 不校验 `exp` | token 永不过期 | 必须查 |
| `exp` 用毫秒 | 校验永远通过 | unix **秒** |
| 自家实现用于生产 | 边界情况漏 | 用 PyJWT/python-jose |
| 密钥硬编码进仓库 | 泄露 | 环境变量/密钥服务 |
| 密钥太短 | 可暴力 | ≥32 字节随机 |
| 明文存密码 | 拖库即失守 | pbkdf2/bcrypt/argon2 |

## 毕业自查

- [ ] 能手算三段结构并解释签名输入
- [ ] 能解释为什么 payload 不算机密
- [ ] 能写出 `alg` 白名单校验
- [ ] 能区分「签名错」与「已过期」
- [ ] 能说明 `compare_digest` 的必要性
- [ ] 能说出为什么生产不用手写
- [ ] 动手题一：把 `exp` 改成可配置 TTL 并在响应里回 `expires_in`
- [ ] 动手题二：加 `refresh_token`（长 TTL、单独 `typ`）

> 想看 base64url 的填充规则、HS256 vs RS256 的取舍、`jti`/`aud`/`iss` 校验、PyJWT 的等价写法、18 条坑，继续读 [`base.md`](./base.md)。