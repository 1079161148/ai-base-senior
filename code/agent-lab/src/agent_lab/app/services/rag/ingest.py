"""摄入管线：文档 → 解析 → 分块 → 嵌入 → 存 pgvector。

pg 连接由内部自己管理，调用方不需要传连接。

注意：所有文本字段在入库前会滤除 \\x00 NULL 字节。
PostgreSQL TEXT 不接受这个字符，出现则整行写入失败。
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import jieba

from . import chunker, embedder, store
from .store import StoredChunk

logger = logging.getLogger(__name__)


def _sanitize_text(s: str) -> str:
    """滤除 \\x00 字节。守护整个管线入口，确保下游不用各自担心。"""
    return s.replace("\x00", "")


async def _pg():
    """从全局池拿一个连接。"""
    from ...core.pg import _pool_for_fastapi as _pg_pool

    if _pg_pool is None:
        raise RuntimeError("pg pool 尚未创建")
    return _pg_pool


async def ingest_text(
    *,
    text: str,
    title: str,
    source: str,
    doc_type: str,
    user_id: str = "",
) -> dict[str, object]:
    """把一段文本摄入 RAG 索引。返回 doc 元数据。"""
    pool = await _pg()
    async with pool.acquire() as pg:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        info = embedder.model_info()
        # doc_id 必须把 user_id 算进去：只哈希文件名的话，
        # 两个用户各传一份 readme.md 会得到同一个 id，
        # 后传的"覆盖"前一个 —— 表现为别人的文档凭空消失。
        doc_id = _doc_id(source, user_id)

        # 入口消毒：所有下游操作（分块/jieba/嵌入）都在消毒后的文本上执行
        text = _sanitize_text(text)
        title = _sanitize_text(title)

        # 1. 分块
        if doc_type == "md":
            selected = chunker.chunk_markdown(text, title)
        else:
            selected = chunker.chunk_text(text, title)

        # 短文也应有索引能力：如果没切出块（正文全是代码块、或短到一行），
        # 那就把全文当成一块塞进去。这样"就一行标题"的文档也能搜到。
        if not selected:
            from .chunker import ChunkSelection

            content = f"来自《{title}》正文：\n\n{text}"
            selected = [ChunkSelection(heading="正文", raw=text, content=content)]

        # 2. 嵌入
        contents = [s.content for s in selected]
        embeddings = await embedder.embed_passages(contents)

        # 3. 分词（BM25 用）
        stored: list[StoredChunk] = []
        for i, sel in enumerate(selected):
            tokens = list(jieba.cut_for_search(sel.raw))
            stored.append(
                StoredChunk(
                    id=f"{doc_id}#{i:04d}",
                    doc_id=doc_id,
                    chunk_index=i,
                    heading=sel.heading,
                    content=sel.content,
                    raw=sel.raw,
                    tokens=tokens,
                )
            )

        # 4. 写入 pgvector：先清旧数据，再写新的（覆盖式更新）
        # doc_id 已含 user_id，所以这里的删除只可能命中自己的旧版本
        await store.delete_document(pg, doc_id, user_id=user_id)

        meta = {
            "id": doc_id,
            "user_id": user_id,
            "title": title,
            "source": source,
            "doc_type": doc_type,
            "char_count": len(text),
            "chunk_count": len(stored),
            "embed_model": info["name"],
            "created_at": now,
        }
        await store.insert_document(pg, meta)
        await store.insert_chunks(pg, stored, embeddings, now)

        logger.info(
            "摄入完成：%s [%s] → %d 块, %d 字",
            title, doc_id, len(stored), len(text),
        )
        return meta


async def ingest_file(filepath: str | Path, *, user_id: str = "") -> dict[str, object]:
    """从文件路径摄入（自动判断类型）。"""
    path = Path(filepath)
    source = path.name
    title = path.stem

    if source.endswith(".md") or source.endswith(".txt"):
        text = await asyncio.to_thread(path.read_text, encoding="utf-8")
        doc_type = source[-2:].lstrip(".")
    elif source.endswith(".pdf"):
        import pymupdf

        def _read_pdf() -> str:
            pages: list[str] = []
            with pymupdf.open(str(path)) as doc:
                for page in doc:
                    t = page.get_text()
                    if t:
                        pages.append(t)
            return "\n\n".join(pages)

        text = await asyncio.to_thread(_read_pdf)
        doc_type = "pdf"
    else:
        raise ValueError(f"不支持的文件类型：{source}")

    return await ingest_text(
        text=text, title=title, source=source, doc_type=doc_type, user_id=user_id,
    )


def _doc_id(source: str, user_id: str = "") -> str:
    """文档 id = hash(用户 + 文件名)。

    同一用户重传同名文件走覆盖（幂等），不同用户互不影响。
    """
    return hashlib.sha256(f"{user_id}|{source}".encode()).hexdigest()[:12]