"""第 29 章 · 表单 + 文件组合（multipart 进阶）。

核心：一次 `multipart/form-data` 请求里可以同时有普通字段和多个文件。
      `list[UploadFile]` 接多文件，`UploadFile | None` 接可选单文件；
      文件与字段都来自同一个请求体，**不能**再混一个 JSON 模型（第 27 章的坑）。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

app = FastAPI(title="第 29 章 · 表单与文件组合", version="0.1.0")

_MAX_FILES = 3


# ============================================================
# 1. 多文件 + 说明字段
# ============================================================
@app.post("/upload/many", tags=["组合"], summary="多文件 + 备注")
async def upload_many(
    files: Annotated[list[UploadFile], File(description="可一次传多个")],
    note: Annotated[str | None, Form(description="附件说明")] = None,
) -> dict[str, Any]:
    """【作用】`list[UploadFile]` 接收**同名** part 的多次出现

    【实测】3 个文件 → `count=3`，顺序与发送顺序一致
    【注意】不传文件 → 422 `missing`（列表默认不是空列表）
    """
    infos = []
    for file in files:
        data = await file.read()
        infos.append({"filename": file.filename, "size": len(data)})
    return {"count": len(files), "note": note, "files": infos}


# ============================================================
# 2. 可选单文件
# ============================================================
@app.post("/upload/optional", tags=["组合"], summary="可选文件")
async def upload_optional(
    file: Annotated[UploadFile | None, File()] = None,
) -> dict[str, Any]:
    """【作用】`UploadFile | None = None`：不传文件也返回 200

    【实测】不传 → `{"file": None}`；传了 → 正常返回大小
    【注意】`list[UploadFile]` 若也想可选，用 `= []`，但空列表语义容易误导客户端
    """
    if file is None:
        return {"file": None}
    data = await file.read()
    return {"file": {"filename": file.filename, "size": len(data)}}


# ============================================================
# 3. 必填封面 + 可选附件 + 普通字段
# ============================================================
@app.post("/upload/mixed", tags=["组合"], summary="封面必填、附件可选")
async def upload_mixed(
    title: Annotated[str, Form(min_length=1, max_length=50, description="标题")],
    cover: Annotated[UploadFile, File(description="封面（必填）")],
    attachments: Annotated[list[UploadFile], File(description="附件（可多个，可不传）")] = [],
) -> dict[str, Any]:
    """【作用】三种参数并存：表单字段、必填文件、可选文件列表

    【实测】`attachments` 不传时是 `[]`，不会 422
    【注意】可变默认值 `= []` 在 FastAPI 里有特殊处理，不会被多个请求共享
    """
    cover_data = await cover.read()
    names = [item.filename for item in attachments]
    return {
        "title": title,
        "cover": {"filename": cover.filename, "size": len(cover_data)},
        "attachments": names,
    }


# ============================================================
# 4. 文件数量限制（应用层校验）
# ============================================================
@app.post("/upload/limited", tags=["组合"], summary="最多 3 个文件")
async def upload_limited(
    files: Annotated[list[UploadFile], File()],
) -> dict[str, Any]:
    """【作用】FastAPI 不提供「列表长度上限」，只能自己判

    【实测】传 4 个 → 413（这里用的 413，也可用 422/400，团队统一即可）
    """
    if len(files) > _MAX_FILES:
        raise HTTPException(status_code=413, detail=f"最多 {_MAX_FILES} 个文件")
    sizes = [(await file.read()) for file in files]
    return {"count": len(files), "sizes": [len(item) for item in sizes]}


# ============================================================
# 5. list[bytes]：小文件批量
# ============================================================
@app.post("/upload/many-bytes", tags=["组合"], summary="list[bytes]")
def upload_many_bytes(
    files: Annotated[list[bytes], File()],
) -> dict[str, Any]:
    """【注意】`list[bytes]` 会把每个文件全读进内存，只适合小批量小文件"""
    return {"count": len(files), "sizes": [len(item) for item in files]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)