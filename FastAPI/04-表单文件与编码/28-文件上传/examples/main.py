"""第 28 章 · 文件上传（File / UploadFile）。

核心：文件走 `multipart/form-data`。小文件可用 `bytes`，**大文件必须用 `UploadFile`**
      （它把内容放在 SpooledTemporaryFile 里，超过 1MB 自动落盘，不撑爆内存）。
      文件名与 `content_type` 都由客户端提供，**不可信**，只能用来展示。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, UploadFile

app = FastAPI(title="第 28 章 · 文件上传", version="0.1.0")


# ============================================================
# 1. UploadFile：最常用的方式
# ============================================================
@app.post("/upload/text", tags=["上传"], summary="上传文本文件并返回大小")
async def upload_text(
    file: Annotated[UploadFile, File(description="要上传的文本文件")],
) -> dict[str, Any]:
    """【作用】`UploadFile` 是异步可读的文件对象，`await file.read()` 拿全部内容

    【实测】返回 `filename`/`content_type`/`size`/`preview`
    【注意】`file.read()` 读完后流就空了，再读得到 `b""`，要重读需 `await file.seek(0)`
    """
    data = await file.read()
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(data),
        "preview": data[:32].decode("utf-8", errors="replace"),
    }


# ============================================================
# 2. bytes：小文件简化写法
# ============================================================
@app.post("/upload/bytes", tags=["上传"], summary="bytes 版本")
def upload_bytes(data: Annotated[bytes, File(description="文件内容")]) -> dict[str, int]:
    """【作用】`bytes` 直接把整个文件读进内存，写法最简单

    【注意】大文件会直接吃内存，**只在确定小于几 MB 时用**
    """
    return {"size": len(data)}


# ============================================================
# 3. 流式读取：分块 + 回退
# ============================================================
@app.post("/upload/chunks", tags=["上传"], summary="分块读取")
async def upload_chunks(file: Annotated[UploadFile, File()]) -> dict[str, Any]:
    """【作用】`await file.read(n)` 每次只读 n 字节，适合边读边处理（如哈希、写盘）

    【实测】读 4 字节后再 `seek(0)` 重读，能拿到完整内容
    【注意】分块读不会把整个文件放内存，但仍受 SpooledTemporaryFile 阈值影响
    """
    head = await file.read(4)
    await file.seek(0)
    total = 0
    while chunk := await file.read(8):
        total += len(chunk)
    await file.close()
    return {"head": head.decode("utf-8", errors="replace"), "total": total}


# ============================================================
# 4. SpooledTemporaryFile：什么时候落盘
# ============================================================
@app.post("/upload/spool", tags=["上传"], summary="观察落盘行为")
async def upload_spool(file: Annotated[UploadFile, File()]) -> dict[str, Any]:
    """【作用】Starlette 的 `UploadFile.file` 是 `SpooledTemporaryFile(max_size=1MB)`

    【实测】小文件 `_rolled` 为 False（在内存），>1MB 变 True（已落盘）
    【注意】`_rolled` 是 CPython 实现细节，只用于演示，业务代码不要依赖
    """
    data = await file.read()
    rolled = getattr(file.file, "_rolled", None)
    return {"size": len(data), "rolled_to_disk": rolled}


# ============================================================
# 5. 文件名不可信
# ============================================================
@app.post("/upload/safe-name", tags=["安全"], summary="清洗文件名")
async def safe_name(file: Annotated[UploadFile, File()]) -> dict[str, str]:
    """【作用】客户端可以传任意 `filename`，包括 `../../etc/passwd`

    【实测】原样返回的 `filename` 会带 `..\\..\\`，只取 `Path(...).name` 才安全
    【注意】真实项目还要重命名存储（UUID），展示名单独存库
    """
    given = file.filename or ""
    return {"given": given, "basename": Path(given).name}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)