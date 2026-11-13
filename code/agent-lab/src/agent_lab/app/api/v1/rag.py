"""RAG 文档上传与查询接口（S9 起按用户隔离）。

文件上传的临时存储：用系统临时目录（跨平台且不会进版本库）。
生产环境应换成 OSS / 持久文件存储，但学习阶段 tmpdir 完全够用。

**隔离的三道关**：
1. 上传时把 user_id 写进 documents 表，并参与 doc_id 计算（防同名覆盖）
2. 列表 / 预览 / 删除都带 user_id 条件
3. 检索时 JOIN documents 过滤 —— 否则模型会读到别人的文档
"""

import tempfile
from pathlib import Path

import asyncpg
from fastapi import APIRouter, Depends, File, UploadFile, status

from ...core.errors import ApiError
from ...core.pg import get_pg_fastapi
from ...core.security import CurrentUserDep
from ...services.rag import ingest, store

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/upload", summary="上传文档并建立索引")
async def upload(
    user: CurrentUserDep,
    file: UploadFile = File(...),
) -> dict[str, object]:
    """接受 md / txt / pdf，写入临时文件后摄入。

    同一个用户重复上传同名文件会覆盖旧索引；不同用户互不影响。
    """
    allowed = (".md", ".txt", ".pdf")
    name = file.filename or ""
    suffix = Path(name).suffix.lower()
    if suffix not in allowed:
        raise ApiError(400, "UNSUPPORTED_FORMAT", f"仅支持 md、txt、pdf，不接受 {suffix}")

    raw = await file.read()
    if not raw:
        raise ApiError(400, "EMPTY_FILE", "文件为空")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        meta = await ingest.ingest_file(tmp_path, user_id=user.id)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "ok": True,
        "doc_id": meta["id"],
        "title": meta["title"],
        "chunks": meta["chunk_count"],
        "chars": meta["char_count"],
    }


@router.get("/documents", summary="已索引的文档列表")
async def list_documents(
    user: CurrentUserDep,
    pg: asyncpg.Connection = Depends(get_pg_fastapi),
) -> list[dict[str, object]]:
    return await store.list_all_documents(pg, user_id=user.id)


@router.get("/documents/{doc_id}/chunks", summary="文档片段预览")
async def list_document_chunks(
    doc_id: str,
    user: CurrentUserDep,
    limit: int = 20,
    offset: int = 0,
    pg: asyncpg.Connection = Depends(get_pg_fastapi),
) -> dict[str, object]:
    """返回该文档的 chunk 正文，供前端预览「传进来的到底是什么内容」。

    raw 是原文（用户看到的版本），content 是拼接了上下文的增强版（喂给模型的版本），
    两者不一样，这里给前端 raw。
    """
    safe_limit = max(1, min(limit, 100))
    chunks = await store.list_document_chunks(
        pg, doc_id, safe_limit, max(0, offset), user_id=user.id
    )
    return {
        "doc_id": doc_id,
        "chunks": [
            {"chunk_index": c.chunk_index, "heading": c.heading, "text": c.raw}
            for c in chunks
        ],
    }


@router.delete(
    "/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除文档及其索引",
)
async def delete_document(
    doc_id: str,
    user: CurrentUserDep,
    pg: asyncpg.Connection = Depends(get_pg_fastapi),
) -> None:
    # 幂等：删一个不存在的 id 也返回 204，前端不需要区分「已删」和「本来没有」
    await store.delete_document(pg, doc_id, user_id=user.id)
