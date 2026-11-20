"""第 25 章 · 直接返回 Response。

核心：需要「逐字节控制响应」时（文件下载、流式、重定向），返回 `Response` 子类，
      代价是**绕过响应模型**：不校验、不过滤、文档也不会自动生成。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from pydantic import BaseModel

app = FastAPI(title="第 25 章 · 直接返回 Response", version="0.1.0")

ASSETS = Path(__file__).parent / "assets"


class ItemOut(BaseModel):
    id: int
    name: str


# ============================================================
# 1. 文件下载：FileResponse
# ============================================================
@app.get("/download/{filename}", tags=["文件"], summary="下载文件")
def download(filename: str) -> FileResponse:
    """【作用】`FileResponse` 自动设置 `Content-Length`、`Content-Type`，并支持 Range

    【实测】`filename=hello.txt` → `content-type: text/plain; charset=utf-8`
    【实测】`filename=报告.txt` → `Content-Disposition` 用 RFC 5987 编码（见 verify）
    【注意】这里没有做路径穿越防护 —— 真实项目必须校验文件名（见 base.md 4.4）
    """
    path = ASSETS / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=filename)


# ============================================================
# 2. 流式输出：StreamingResponse
# ============================================================
def _chunks() -> Any:
    """生成器：每次 yield 一段字节。"""
    for i in range(3):
        yield f"chunk-{i}\n"


@app.get("/stream", tags=["流式"], summary="流式输出")
def stream() -> StreamingResponse:
    """【实测】没有 `Content-Length`，用 chunked 传输；客户端逐段读取

    【为什么】大文件/大导出不能先拼成完整字符串，否则内存爆掉
    【注意】流式响应里抛异常无法再改状态码（头已发出）
    """
    return StreamingResponse(_chunks(), media_type="text/plain")


@app.get("/stream/abort", tags=["流式"], summary="流式过程中出错")
def stream_abort() -> StreamingResponse:
    """【实测】yield 之后抛异常 → 客户端拿到部分内容后连接中断，状态码仍是 200"""

    def gen() -> Any:
        yield "part-1\n"
        raise RuntimeError("下游断流")

    return StreamingResponse(gen(), media_type="text/plain")


# ============================================================
# 3. 重定向
# ============================================================
@app.get("/old-path", tags=["重定向"], summary="默认 307")
def old_path() -> RedirectResponse:
    """【实测】`RedirectResponse` 默认状态码是 **307**，不是 302"""
    return RedirectResponse("/new-path")


@app.get("/old-path-302", status_code=302, tags=["重定向"], summary="显式 302")
def old_path_302() -> RedirectResponse:
    """【作用】`status_code=302` 里的码会被 RedirectResponse 采用"""
    return RedirectResponse("/new-path", status_code=302)


@app.get("/new-path", tags=["重定向"], summary="重定向目标")
def new_path() -> dict[str, str]:
    return {"path": "/new-path"}


# ============================================================
# 4. response_class：换默认响应类
# ============================================================
@app.get("/text", response_class=PlainTextResponse, tags=["响应类"], summary="纯文本")
def text() -> str:
    """【实测】`response_class=PlainTextResponse` + 返回 str → `text/plain; charset=utf-8`

    【注意】它同时改变 OpenAPI 里该响应的 `content` 类型
    """
    return "纯文本内容"


@app.get("/html", response_class=HTMLResponse, tags=["响应类"], summary="HTML")
def html() -> str:
    return "<h1>hello</h1>"


# ============================================================
# 5. 自定义 Response 子类
# ============================================================
class XmlResponse(Response):
    media_type = "application/xml"


@app.get("/xml", tags=["响应类"], summary="自定义响应类")
def xml() -> XmlResponse:
    """【作用】继承 `Response` 并固定 `media_type`，比每次传参更省心"""
    return XmlResponse("<item><id>1</id></item>")


# ============================================================
# 6. Response 与 response_model 同时存在
# ============================================================
@app.get("/ignore-model", response_model=ItemOut, tags=["反例"], summary="模型被绕过")
def ignore_model() -> Any:
    """【实测】返回 `PlainTextResponse` 时，`response_model` 完全不生效

    【结论】声明了 `response_model` 又返回 `Response`，文档与现实不符
    """
    return PlainTextResponse("这不是 JSON，也不会被 ItemOut 校验")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level=sys.argv[1] if len(sys.argv) > 1 else "info")
