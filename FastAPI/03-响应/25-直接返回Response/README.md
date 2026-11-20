# 25 直接返回 Response

## 一句话结论

需要逐字节控制响应时（文件下载、流式、重定向、非 JSON），返回 `Response` 子类。代价明确：**绕过响应模型**——不校验、不过滤、文档不自动生成。重定向默认是 **307**；流式一旦开始发头，中途出错也改不了状态码。

学完这一章，你能：下载文件（含中文文件名编码）、流式输出大结果、正确重定向、用 `response_class` 换媒体类型、自定义 `Response` 子类。

## 最小可运行案例

```python
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse, StreamingResponse

app = FastAPI()
ASSETS = Path(__file__).parent / "assets"


@app.get("/download/{filename}")
def download(filename: str) -> FileResponse:
    path = ASSETS / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=filename)


@app.get("/stream")
def stream() -> StreamingResponse:
    def gen() -> Any:
        for i in range(3):
            yield f"chunk-{i}\n"

    return StreamingResponse(gen(), media_type="text/plain")


@app.get("/old")
def old() -> RedirectResponse:
    return RedirectResponse("/new")          # 默认 307


@app.get("/text", response_class=PlainTextResponse)
def text() -> str:
    return "纯文本"
```

完整版本（中文文件名、流式中断、自定义响应类、模型被绕过）见 `examples/main.py`。

## 怎么跑

```powershell
cd "03-响应\25-直接返回Response\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 文件下载 -> content-type=text/plain; charset=utf-8
[PASS] ASCII 文件名 -> content-disposition=attachment; filename="hello.txt"
[PASS] 中文文件名编码 -> RFC 5987 编码：attachment; filename*=utf-8''%E6%8A%A5%E5%91%8A.txt
[PASS] 文件不存在 404 -> 404
[PASS] 流式无 content-length -> 无 content-length，3 段拼接
[PASS] 流式中断 -> 200 + 部分内容（状态码已发出）
[PASS] 重定向默认 307 -> 307 + Location
[PASS] 重定向 302 -> 302
[PASS] response_class -> content-type=text/plain; charset=utf-8
[PASS] 自定义响应类 -> application/xml
[PASS] response_model 被绕过 -> 纯文本原样返回，未按 ItemOut 校验

结果：11/11 通过
```

## 核心 API 速查

| 场景 | 类 | 关键参数 |
| --- | --- | --- |
| 下载文件 | `FileResponse(path, filename=...)` | 自动 `Content-Length`/`Content-Type`/Range |
| 大结果流式 | `StreamingResponse(gen(), media_type=...)` | 无 `Content-Length`，chunked |
| 重定向 | `RedirectResponse(url)` | 默认 **307** |
| 纯文本 | `PlainTextResponse("...")` | `text/plain; charset=utf-8` |
| HTML | `HTMLResponse(...)` | `text/html` |
| 自定义 | `class XmlResponse(Response): media_type = "application/xml"` | 复用媒体类型 |
| 换默认类 | `@app.get(..., response_class=PlainTextResponse)` | 同时改 OpenAPI |

| 返回类型 | 走响应模型 | 有无 `Content-Length` |
| --- | --- | --- |
| 模型 / dict | ✅ | 有 |
| `FileResponse` | ❌ | 有 |
| `StreamingResponse` | ❌ | 无（chunked）|
| `RedirectResponse` | ❌ | 无 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 声明 `response_model` 又返回 `Response` | 文档与行为不符 | 去掉模型或用真实结构 |
| 以为 `RedirectResponse` 是 302 | 实测默认 **307** | 需要 302 就显式传 |
| 307 与 302 混用 | 前者保留方法（POST 重发 POST）| 按语义选 |
| 大文件用 `FileResponse` 之外的读法 | 整个文件进内存 | `FileResponse`/`StreamingResponse` |
| 流式中途抛异常想返回 500 | 头已发，改不了 | 先做完整校验再流式 |
| 文件名直接拼路径 | 路径穿越（`../../etc/passwd`）| 白名单/`Path.name` 校验 |
| 中文文件名手拼 `Content-Disposition` | 客户端乱码 | 用 `filename=` 让框架走 RFC 5987 |
| 以为 `response_class` 只影响文档 | 它也改真实媒体类型 | 两边一致 |
| 流式响应里做重计算 | 阻塞事件循环 | 用异步生成器/线程池 |
| 忘了关文件句柄 | 句柄泄漏 | `FileResponse` 会管理，别自己 open |

## 毕业自查

- [ ] 能说出哪些场景必须返回 `Response`
- [ ] 能说出返回 `Response` 后哪些能力消失
- [ ] 能写出文件下载并处理不存在
- [ ] 能写出流式输出并解释为什么没有 `Content-Length`
- [ ] 能说出 307 与 302 的差别
- [ ] 能解释中文文件名为什么需要 RFC 5987
- [ ] 动手题一：给下载加 `Content-Disposition: inline`，让浏览器直接预览
- [ ] 动手题二：把 `/stream` 改成异步生成器，并加 1 秒间隔

> 想看 Range 请求、路径穿越防护、异步生成器、CSV 导出、20 条坑，继续读 [`base.md`](./base.md)。
