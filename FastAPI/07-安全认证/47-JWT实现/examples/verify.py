"""第 47 章 · 自动验收。运行：python verify.py"""

import base64
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def b64(obj: dict) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(obj, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()


def login() -> str:
    r = client.post("/token", data={"username": "alice", "password": "alice123"})
    assert r.status_code == 200, (r.status_code, r.text)
    return r.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def check_token_shape() -> str:
    """三段、无 `=` 填充。"""
    token = login()
    parts = token.split(".")
    assert len(parts) == 3, parts
    assert "=" not in token, token
    return f"segments=3, len={len(token)}"


def check_header_and_claims() -> str:
    """header 是 HS256/JWT；payload 有 sub/iat/exp。"""
    token = login()
    body = client.get("/debug/payload", params={"token": token}).json()
    assert body["header"] == {"alg": "HS256", "typ": "JWT"}, body["header"]
    claims = body["payload"]
    assert claims["sub"] == "alice", claims
    assert isinstance(claims["exp"], int) and claims["exp"] > time.time(), claims
    assert isinstance(claims["iat"], int) and claims["iat"] <= time.time(), claims
    return f'header={body["header"]}, claims={sorted(claims)}'


def check_payload_is_plaintext() -> str:
    """payload 不验签就能读（JWT 不是加密）。"""
    token = login()
    payload_b64 = token.split(".")[1]
    padding = "=" * (-len(payload_b64) % 4)
    raw = base64.urlsafe_b64decode(payload_b64 + padding)
    assert json.loads(raw)["sub"] == "alice", raw
    return "payload 可直接 base64 解码"


def check_me_ok() -> str:
    """有效 token → 200。"""
    r = client.get("/users/me", headers=auth(login()))
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json() == {"username": "alice", "full_name": "Alice Chen"}, r.json()
    return "200 alice"


def check_bad_signature() -> str:
    """签名被改 → 401 签名不符。"""
    parts = login().split(".")
    bad = f'{parts[0]}.{parts[1]}.{"A" * len(parts[2])}'
    r = client.get("/users/me", headers=auth(bad))
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json()["detail"] == "token 无效：签名不符", r.json()
    return "401 签名不符"


def check_tampered_payload() -> str:
    """改 payload 保留原签名 → 401（证明防篡改）。"""
    parts = login().split(".")
    tampered = f'{parts[0]}.{b64({"sub": "bob", "exp": 9999999999})}.{parts[2]}'
    r = client.get("/users/me", headers=auth(tampered))
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json()["detail"] == "token 无效：签名不符", r.json()
    return "改 sub 后签名不符"


def check_alg_none_rejected() -> str:
    """`alg: none` 攻击被拒（必须校验头）。"""
    token = f'{b64({"alg": "none", "typ": "JWT"})}.{b64({"sub": "alice", "exp": 9999999999})}.'
    r = client.get("/users/me", headers=auth(token))
    assert r.status_code == 401, (r.status_code, r.text)
    assert "不支持的算法" in r.json()["detail"], r.json()
    return "401 不支持的算法 'none'"


def check_expired_token() -> str:
    """exp 已过 → 401 已过期（不是签名错）。"""
    token = client.post("/token/expired").json()["access_token"]
    r = client.get("/users/me", headers=auth(token))
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json()["detail"] == "token 无效：已过期", r.json()
    return "401 已过期"


def check_malformed_token() -> str:
    """段数不对 → 401。"""
    r = client.get("/users/me", headers=auth("a.b"))
    assert r.status_code == 401, (r.status_code, r.text)
    assert "三段" in r.json()["detail"], r.json()
    return "401 token 必须是三段"


def check_wrong_secret() -> str:
    """换密钥签的 token 验不过。"""
    original = main.SECRET_KEY
    try:
        main.SECRET_KEY = "another-secret-key-0000000000000000"
        forged = main.create_access_token({"sub": "alice"})
    finally:
        main.SECRET_KEY = original
    r = client.get("/users/me", headers=auth(forged))
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json()["detail"] == "token 无效：签名不符", r.json()
    return "异密钥签名被拒"


def check_challenge_header() -> str:
    """401 带 `WWW-Authenticate: Bearer error="invalid_token"`。"""
    r = client.get("/users/me", headers=auth("x.y.z"))
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == 'Bearer error="invalid_token"', dict(r.headers)
    return 'Bearer error="invalid_token"'


def check_password_salt() -> str:
    """同一密码两次哈希不同；校验正确。"""
    first = main.hash_password("same-pass")
    second = main.hash_password("same-pass")
    assert first != second, (first, second)
    assert main.verify_password("same-pass", first) is True
    assert main.verify_password("wrong", first) is False
    return "salt 随机，校验通过"


def check_wrong_password_400() -> str:
    """密码错 → 400。"""
    r = client.post("/token", data={"username": "alice", "password": "bad"})
    assert r.status_code == 400, (r.status_code, r.text)
    return "400"


def check_expires_in() -> str:
    """响应带 `expires_in`（秒）。"""
    body = client.post("/token", data={"username": "alice", "password": "alice123"}).json()
    assert set(body) == {"access_token", "token_type", "expires_in"}, body
    assert body["expires_in"] == main.ACCESS_TOKEN_EXPIRE_MINUTES * 60, body
    return f'expires_in={body["expires_in"]}'


CHECKS = [
    ("token 结构", check_token_shape),
    ("header/claims", check_header_and_claims),
    ("payload 明文", check_payload_is_plaintext),
    ("有效 token", check_me_ok),
    ("签名错", check_bad_signature),
    ("篡改 payload", check_tampered_payload),
    ("alg=none", check_alg_none_rejected),
    ("过期", check_expired_token),
    ("格式错", check_malformed_token),
    ("异密钥", check_wrong_secret),
    ("challenge 头", check_challenge_header),
    ("密码 salt", check_password_salt),
    ("密码错", check_wrong_password_400),
    ("expires_in", check_expires_in),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except AssertionError as exc:
            failures += 1
            print(f"[FAIL] {name} -> {exc}")
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())