"""第 29 章 · 自动验收。运行：python verify.py"""

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


def check_many_files() -> str:
    """多文件 + 备注：数量、顺序、大小都对。"""
    files = [
        ("files", ("a.txt", b"aaa", "text/plain")),
        ("files", ("b.txt", b"bbbb", "text/plain")),
        ("files", ("c.txt", b"ccccc", "text/plain")),
    ]
    r = client.post("/upload/many", files=files, data={"note": "三份附件"})
    assert r.status_code == 200, (r.status_code, r.text)
    data = r.json()
    assert data["count"] == 3, data
    assert data["note"] == "三份附件", data
    assert [f["filename"] for f in data["files"]] == ["a.txt", "b.txt", "c.txt"], data
    assert [f["size"] for f in data["files"]] == [3, 4, 5], data
    return "3 个文件顺序与大小正确"


def check_many_files_missing() -> str:
    """list[UploadFile] 不传文件 → 422 missing。"""
    r = client.post("/upload/many")
    assert r.status_code == 422, (r.status_code, r.text)
    err = first_error(r)
    assert err["loc"] == ["body", "files"], err
    assert err["type"] == "missing", err
    return f'loc={err["loc"]}'


def check_single_file_to_list() -> str:
    """只传 1 个文件给 list：FastAPI 会当成 1 项列表。"""
    r = client.post("/upload/many", files=[("files", ("only.txt", b"x", "text/plain"))])
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json()["count"] == 1, r.json()
    return "单文件 → count=1（不报错）"


def check_optional_absent() -> str:
    """可选文件不传 → 200 且 file=None。"""
    r = client.post("/upload/optional")
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json() == {"file": None}, r.json()
    return "file=None"


def check_optional_present() -> str:
    """可选文件传了 → 正常返回。"""
    r = client.post("/upload/optional", files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 200, r.text
    assert r.json()["file"]["size"] == 5, r.json()
    return "file.size=5"


def check_mixed_all() -> str:
    """必填字段 + 必填文件 + 可选文件列表。"""
    files = [
        ("cover", ("cover.png", b"PNG", "image/png")),
        ("attachments", ("a.pdf", b"PDF1", "application/pdf")),
        ("attachments", ("b.pdf", b"PDF22", "application/pdf")),
    ]
    r = client.post("/upload/mixed", files=files, data={"title": "季度报告"})
    assert r.status_code == 200, (r.status_code, r.text)
    data = r.json()
    assert data["title"] == "季度报告", data
    assert data["cover"] == {"filename": "cover.png", "size": 3}, data
    assert data["attachments"] == ["a.pdf", "b.pdf"], data
    return "封面 3 字节 + 2 个附件"


def check_mixed_no_attachments() -> str:
    """attachments 不传 → 默认空列表，不 422。"""
    r = client.post("/upload/mixed", files={"cover": ("c.png", b"x", "image/png")}, data={"title": "t"})
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json()["attachments"] == [], r.json()
    return "attachments=[]"


def check_mixed_missing_title() -> str:
    """缺少普通表单字段 → 422。"""
    r = client.post("/upload/mixed", files={"cover": ("c.png", b"x", "image/png")})
    assert r.status_code == 422, (r.status_code, r.text)
    assert first_error(r)["loc"] == ["body", "title"], first_error(r)
    return "title 缺失 422"


def check_limit_exceeded() -> str:
    """文件数超限 → 413。"""
    files = [("files", (f"{i}.txt", b"x", "text/plain")) for i in range(4)]
    r = client.post("/upload/limited", files=files)
    assert r.status_code == 413, (r.status_code, r.text)
    assert r.json()["detail"] == "最多 3 个文件", r.json()
    return "4 个 → 413"


def check_limit_ok() -> str:
    """刚好 3 个 → 通过。"""
    files = [("files", (f"{i}.txt", b"x" * (i + 1), "text/plain")) for i in range(3)]
    r = client.post("/upload/limited", files=files)
    assert r.status_code == 200, r.text
    assert r.json() == {"count": 3, "sizes": [1, 2, 3]}, r.json()
    return "sizes=[1,2,3]"


def check_many_bytes() -> str:
    """list[bytes] 版本。"""
    files = [
        ("files", ("a.bin", b"12", "application/octet-stream")),
        ("files", ("b.bin", b"345", "application/octet-stream")),
    ]
    r = client.post("/upload/many-bytes", files=files)
    assert r.status_code == 200, r.text
    assert r.json() == {"count": 2, "sizes": [2, 3]}, r.json()
    return "sizes=[2,3]"


def check_openapi_array_schema() -> str:
    """OpenAPI：多文件字段是 array（items 为 string + contentMediaType）。"""
    schema = client.get("/openapi.json").json()
    body = schema["paths"]["/upload/many"]["post"]["requestBody"]
    ref = body["content"]["multipart/form-data"]["schema"]["$ref"].split("/")[-1]
    prop = schema["components"]["schemas"][ref]["properties"]["files"]
    assert prop["type"] == "array", prop
    item = prop["items"]
    assert item["type"] == "string", item
    assert item.get("contentMediaType") == "application/octet-stream", item
    return f'files.type=array, items.contentMediaType={item.get("contentMediaType")}'


CHECKS = [
    ("多文件 + 备注", check_many_files),
    ("多文件缺失 422", check_many_files_missing),
    ("单文件给 list", check_single_file_to_list),
    ("可选文件不传", check_optional_absent),
    ("可选文件传了", check_optional_present),
    ("混合三者", check_mixed_all),
    ("无附件默认空", check_mixed_no_attachments),
    ("缺普通字段", check_mixed_missing_title),
    ("文件数超限", check_limit_exceeded),
    ("文件数刚好", check_limit_ok),
    ("list[bytes]", check_many_bytes),
    ("OpenAPI array", check_openapi_array_schema),
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