"""第 25 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_file_download() -> str:
    """FileResponse：内容、媒体类型、长度都对。"""
    r = client.get("/download/hello.txt")
    assert r.status_code == 200, (r.status_code, r.text)
    # 【注意】示例文件在 Windows 上写入时是 CRLF，用 strip() 比较更稳
    assert r.text.strip() == "hello from chapter 25", repr(r.text)
    assert r.headers["content-type"].startswith("text/plain"), r.headers["content-type"]
    assert int(r.headers["content-length"]) == len(r.content), r.headers
    return f'content-type={r.headers["content-type"]}'


def check_content_disposition_ascii() -> str:
    """ASCII 文件名：Content-Disposition 直接带 filename。"""
    r = client.get("/download/hello.txt")
    cd = r.headers["content-disposition"]
    assert cd.startswith("attachment"), cd
    assert 'filename="hello.txt"' in cd, cd
    return f"content-disposition={cd}"


def check_content_disposition_unicode() -> str:
    """中文文件名：走 RFC 5987 的 filename* 编码。"""
    r = client.get("/download/报告.txt")
    assert r.status_code == 200, (r.status_code, r.text)
    cd = r.headers["content-disposition"]
    assert "filename*=utf-8''" in cd.lower(), cd
    assert "%E6%8A%A5%E5%91%8A.txt" in cd, cd
    return f"RFC 5987 编码：{cd}"


def check_file_not_found() -> str:
    """文件不存在：404（我们自己判的，不是 FileResponse 抛的）。"""
    r = client.get("/download/nope.txt")
    assert r.status_code == 404, (r.status_code, r.text)
    return "404"


def check_stream_no_content_length() -> str:
    """StreamingResponse：没有 Content-Length，内容是分段拼接。"""
    r = client.get("/stream")
    assert r.status_code == 200, r.text
    assert r.text == "chunk-0\nchunk-1\nchunk-2\n", r.text
    assert "content-length" not in {k.lower() for k in r.headers}, dict(r.headers)
    return "无 content-length，3 段拼接"


def check_stream_abort() -> str:
    """流式过程中抛异常：已发出的内容不可撤回。"""
    c = TestClient(main.app, raise_server_exceptions=False)
    r = c.get("/stream/abort")
    assert r.status_code == 200, r.status_code
    assert "part-1" in r.text, r.text
    return "200 + 部分内容（状态码已发出）"


def check_redirect_default_307() -> str:
    """RedirectResponse 默认 307。"""
    r = client.get("/old-path", follow_redirects=False)
    assert r.status_code == 307, r.status_code
    assert r.headers["location"] == "/new-path", r.headers
    return "307 + Location"


def check_redirect_explicit_302() -> str:
    """显式 302 生效。"""
    r = client.get("/old-path-302", follow_redirects=False)
    assert r.status_code == 302, r.status_code
    return "302"


def check_response_class() -> str:
    """response_class 改变媒体类型与 OpenAPI content。"""
    r = client.get("/text")
    assert r.headers["content-type"].startswith("text/plain"), r.headers["content-type"]
    assert r.text == "纯文本内容", r.text

    schema = client.get("/openapi.json").json()
    content = schema["paths"]["/text"]["get"]["responses"]["200"]["content"]
    assert any("text/plain" in key for key in content), content
    return f'content-type={r.headers["content-type"]}'


def check_custom_response_subclass() -> str:
    """自定义 Response 子类固定媒体类型。"""
    r = client.get("/xml")
    assert r.headers["content-type"].startswith("application/xml"), r.headers["content-type"]
    assert r.text.startswith("<item>"), r.text
    return "application/xml"


def check_response_model_bypassed() -> str:
    """声明 response_model 却返回 Response：模型不生效。"""
    r = client.get("/ignore-model")
    assert r.status_code == 200, r.status_code
    assert r.headers["content-type"].startswith("text/plain"), r.headers["content-type"]
    assert r.text == "这不是 JSON，也不会被 ItemOut 校验", r.text
    return "纯文本原样返回，未按 ItemOut 校验"


CHECKS = [
    ("文件下载", check_file_download),
    ("ASCII 文件名", check_content_disposition_ascii),
    ("中文文件名编码", check_content_disposition_unicode),
    ("文件不存在 404", check_file_not_found),
    ("流式无 content-length", check_stream_no_content_length),
    ("流式中断", check_stream_abort),
    ("重定向默认 307", check_redirect_default_307),
    ("重定向 302", check_redirect_explicit_302),
    ("response_class", check_response_class),
    ("自定义响应类", check_custom_response_subclass),
    ("response_model 被绕过", check_response_model_bypassed),
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
