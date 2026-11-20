# 64 WebSocket 鉴权

## 一句话结论

WebSocket 握手就是 HTTP，所以鉴权位置有四种：`?token=`（简单但进日志）、`Authorization` 头（浏览器原生 `WebSocket` **不能**自定义头）、cookie（同域自动带）、首帧鉴权（最灵活，**必须设超时**否则白占连接）。实测四种方式有效时都返回 `{"type":"ready"}`，失败一律 `close(1008)`；首帧超时设为 0.15s 时实测 **153ms** 后收到 `1008 / auth timeout`；鉴权失败只累加 `rejected` 不进 `connected`，成功后断开 `active` 清空、`closed` 累加。

## 最小可运行案例

```python
from fastapi import FastAPI, WebSocket

app = FastAPI()
VALID = "secret-token"


@app.websocket("/ws/echo")
async def echo(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if token != VALID:
        # 不 accept 直接关：握手失败，不占业务连接
        await websocket.close(code=1008, reason="invalid token")
        return

    await websocket.accept()
    while True:
        text = await websocket.receive_text()
        await websocket.send_text(f"echo: {text}")
```

首帧鉴权版本：

```python
import asyncio


@app.websocket("/ws/secure")
async def secure(websocket: WebSocket, timeout: float = 1.0) -> None:
    await websocket.accept()
    try:
        frame = await asyncio.wait_for(websocket.receive_json(), timeout=timeout)
    except TimeoutError:
        await websocket.close(code=1008, reason="auth timeout")
        return

    if frame.get("type") != "auth" or frame.get("token") != VALID:
        await websocket.close(code=1008, reason="invalid token")
        return

    await websocket.send_json({"type": "ready"})
    # ... 业务循环
```

## 怎么跑

```powershell
cd "10-实时流式\64-WebSocket 鉴权\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] query 有效 -> ready / query-user
[PASS] query 缺失 -> 1008 / invalid query token
[PASS] query 错误 -> 1008 / invalid query token
[PASS] header 有效 -> ready / header-user
[PASS] header 缺失 -> 1008 / invalid authorization header
[PASS] cookie 有效 -> ready / cookie-user
[PASS] cookie 缺失 -> 1008 / invalid session cookie
[PASS] 首帧有效 -> ready → pong → echo
[PASS] 首帧 token 错 -> 1008 / invalid token
[PASS] 首帧类型错 -> 1008 / first frame must be auth
[PASS] 首帧超时 -> auth timeout，153ms
[PASS] 拒绝不计连接 -> rejected=2 connected=1
[PASS] 断开清理 -> active ['query-user'] → [], closed=1
[PASS] 双用户隔离 -> alice/bob 各自收到自己的回声

结果：14/14 通过
```

## 核心 API 速查

| 位置 | 读取方式 | 握手前可判 | 浏览器 `WebSocket` 可用 | 会进日志 |
| --- | --- | --- | --- | --- |
| query | `ws.query_params["token"]` | 是 | 是 | **是** |
| header | `ws.headers["authorization"]` | 是 | **否** | 否 |
| cookie | `ws.cookies["session"]` | 是 | 是 | 否 |
| 首帧 | `await ws.receive_json()` | 否 | 是 | 否 |

| 关闭码 | 用途 |
| --- | --- |
| 1008 | 策略拒绝（未登录/无权限）|
| 1000 | 正常关闭 |
| 4001+ | 应用自定义 |

| 实测 | 值 |
| --- | --- |
| query/header/cookie 有效 | 均返回 `ready` |
| 缺失或错误 | 1008 + 具体 reason |
| 首帧超时 0.15s | 153ms 后 1008 `auth timeout` |
| 首帧类型错 | 1008 `first frame must be auth` |
| 拒绝 | `rejected` +1，`connected` 不变 |
| 断开 | `active` 清空，`closed` +1 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 首帧鉴权不设超时 | 攻击者连上不发帧，白占连接 | `asyncio.wait_for` |
| 未鉴权就 `accept()` 且不关 | 连接一直挂着 | 失败立即 `close(1008)` |
| 用 `?token=` 传长期 token | 进访问日志/代理日志 | 短期一次性票据 |
| 浏览器用 `WebSocket` 带 Authorization | 浏览器不支持自定义头 | cookie 或首帧 |
| 鉴权失败返回 200 | 客户端以为成功 | `close(1008)` |
| 只校验首帧不管后续 | 发完 auth 就能任意操作 | 建立会话身份 |
| `finally` 不清 `ACTIVE` | 幽灵用户，广播报错 | 一定 `pop` |
| 用 token 当 key | 同 token 多设备互相覆盖 | 用连接 id |
| 校验放在 `accept` 之后 | 已建立业务连接 | 尽量握手前判 |
| 关闭码用 1006 | 协议错误 | 1000 / 1008 / 4000+ |
| 超时时间太长（30s） | 慢速攻击 | 1~5s |
| 不区分「无 token」和「token 错」 | 排障困难 | reason 写清 |
| 鉴权后不校验 Origin | 跨站劫持 | 校验 `Origin` 白名单 |
| 用 cookie 但不设 SameSite | CSWSH 风险 | `SameSite=Lax/Strict` |
| token 放 URL 又被 CDN 记录 | 泄露 | 改 header/首帧 |
| 多 worker 共享内存统计 | 数字不准 | 外部存储 |

## 毕业自查

- [ ] 能列出四种鉴权位置与各自代价
- [ ] 能解释为什么首帧鉴权必须设超时
- [ ] 能区分「握手前拒绝」与「握手后拒绝」
- [ ] 能写出 `close(1008)` 的完整流程
- [ ] 知道浏览器 `WebSocket` 不能带自定义头
- [ ] 动手题一：把 query 换成本地签发的短期票据
- [ ] 动手题二：加 `Origin` 白名单校验并测跨站连接

> 想看 JWT 校验、`Origin` 与 CSWSH、会话与踢下线、多 worker 状态、令牌续期、18 条坑，继续读 [`base.md`](./base.md)。