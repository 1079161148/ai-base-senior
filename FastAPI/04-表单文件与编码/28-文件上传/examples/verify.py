"""第 28 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def first_error(response) -> dict:  # noqa: ANN001
    detail = response.json()["detail"]
    assert isinstance(detail, list) and detail, detail
    return detail[0]


def check_upload_text() -> str:
    """上传文本：文件名、类型、大小、内容都对。"""
    files = {"file": ("notes.txt", "hello 世界".encode(), "text/plain")}
    r = client.post("/upload/text", files=files)
    assert r.status_code == 200, (r.status_code, r.text)
    data = r.json()
    assert data["filename"] == "notes.txt", data
    assert data["content_type"] == "text/plain", data
    assert data["size"] == len("hello 世界".encode()), data
    assert data["preview"] == "hello 世界", data
    return f'size={data["size"]}，content_type={data["content_type"]}'


def check_openapi_multipart_binary() -> str:
    """OpenAPI：multipart/form-data + string/contentMediaType。

    【实测】FastAPI 0.146 生成的是 JSON Schema 2020-12 写法：
           {"type": "string", "contentMediaType": "application/octet-stream"}
           **不是**旧文档里的 {"type": "string", "format": "binary"}
    """
    schema_json = client.get("/openapi.json").json()
    body = schema_json["paths"]["/upload/text"]["post"]["requestBody"]
    keys = list(body["content"])
    assert keys == ["multipart/form-data"], keys
    ref = body["content"]["multipart/form-data"]["schema"]["$ref"].split("/")[-1]
    prop = schema_json["components"]["schemas"][ref]["properties"]["file"]
    assert prop["type"] == "string", prop
    assert prop.get("contentMediaType") == "application/octet-stream", prop
    return f"{keys[0]} + contentMediaType={prop['contentMediaType']}"


def check_missing_file_422() -> str:
    """完全不带文件 → 422，loc 指向 file。"""
    r = client.post("/upload/text", files={"other": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 422, (r.status_code, r.text)
    err = first_error(r)
    assert err["loc"] == ["body", "file"], err
    assert err["type"] == "missing", err
    return f'loc={err["loc"]}'


def check_bytes_version() -> str:
    """bytes 版本：直接拿到内容长度。"""
    r = client.post("/upload/bytes", files={"data": ("a.bin", b"0123456789", "application/octet-stream")})
    assert r.status_code == 200, r.text
    assert r.json() == {"size": 10}, r.json()
    return "size=10"


def check_empty_file() -> str:
    """空文件：size 为 0，不报错。"""
    r = client.post("/upload/text", files={"file": ("empty.txt", b"", "text/plain")})
    assert r.status_code == 200, r.text
    assert r.json()["size"] == 0, r.json()
    return "size=0"


def check_chunk_read_and_seek() -> str:
    """分块读 + seek(0) 重读。"""
    payload = "abcdefghijkl".encode()
    r = client.post("/upload/chunks", files={"file": ("a.txt", payload, "text/plain")})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["head"] == "abcd", data
    assert data["total"] == 12, data
    return f'head={data["head"]}，total={data["total"]}'


def check_read_twice_is_empty() -> str:
    """读完不 seek 再读：空（流已耗尽）。"""
    import asyncio

    from starlette.datastructures import UploadFile as StarletteUploadFile
    from io import BytesIO

    async def run() -> tuple[int, int]:
        up = StarletteUploadFile(file=BytesIO(b"hello"), filename="a.txt")
        first = await up.read()
        second = await up.read()
        return len(first), len(second)

    first_len, second_len = asyncio.run(run())
    assert (first_len, second_len) == (5, 0), (first_len, second_len)
    return "首次 5 字节，再次 0 字节（需 seek(0)）"


def check_size_attribute() -> str:
    """UploadFile.size 反映总字节数。"""
    payload = b"x" * 1024
    r = client.post("/upload/text", files={"file": ("big.bin", payload, "application/octet-stream")})
    assert r.status_code == 200, r.text
    assert r.json()["size"] == 1024, r.json()
    return "size=1024"


def check_spool_small_stays_memory() -> str:
    """小文件不落盘：_rolled=False。"""
    r = client.post("/upload/spool", files={"file": ("s.txt", b"small", "text/plain")})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["size"] == 5, data
    assert data["rolled_to_disk"] is False, data
    return "5 字节 → rolled_to_disk=False"


def check_spool_large_rolls() -> str:
    """超过 1MB 落盘：_rolled=True。"""
    payload = b"x" * (1024 * 1024 + 1)
    r = client.post("/upload/spool", files={"file": ("big.bin", payload, "application/octet-stream")})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["size"] == len(payload), data
    assert data["rolled_to_disk"] is True, data
    return "1MB+1 字节 → rolled_to_disk=True"


def check_filename_traversal() -> str:
    """文件名可被伪造：基名清洗是必要防护。"""
    bad = "../../etc/passwd"
    r = client.post("/upload/safe-name", files={"file": (bad, b"x", "text/plain")})
    assert r.status_code == 200, r.text
    data = r.json()
    assert ".." in data["given"], data
    assert data["basename"] == "passwd", data
    return f'given={data["given"]} → basename={data["basename"]}'


def check_content_type_is_claimed() -> str:
    """content_type 由客户端声明，可以撒谎。"""
    r = client.post(
        "/upload/text",
        files={"file": ("fake.txt", b"<html>", "text/html")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["content_type"] == "text/html", r.json()
    return "声明 text/html，服务端原样收到（不可信）"


CHECKS = [
    ("上传文本文件", check_upload_text),
    ("OpenAPI multipart/binary", check_openapi_multipart_binary),
    ("缺文件 422", check_missing_file_422),
    ("bytes 版本", check_bytes_version),
    ("空文件", check_empty_file),
    ("分块读 + seek", check_chunk_read_and_seek),
    ("读两次为空", check_read_twice_is_empty),
    ("size 属性", check_size_attribute),
    ("小文件不落盘", check_spool_small_stays_memory),
    ("大文件落盘", check_spool_large_rolls),
    ("文件名穿越", check_filename_traversal),
    ("content_type 不可信", check_content_type_is_claimed),
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