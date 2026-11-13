"""pgvector 存储：文档元数据 + chunk + 向量索引。

为什么用 pgvector 而不是 SQLite BLOB：
1. **HNSW 索引**——暴力检索 O(N)，HNSW O(log N)，量级差在 1000 块开始体现
2. **和业务数据同库**——documents 和 chunks 可以用外键和事务保证一致性
3. **过滤下推**——先按 doc_id/tenant 过滤再算余弦距离，不需要把全部向量拉到内存
"""

import logging
from dataclasses import dataclass

import asyncpg
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StoredChunk:
    id: str
    doc_id: str
    chunk_index: int
    heading: str
    content: str  # 增强后（拼了上下文），用于嵌入与展示给模型
    raw: str      # 原文，用于用户看到的引用
    tokens: list[str]


async def insert_document(pg: asyncpg.Connection, meta: dict[str, object]) -> None:
    await pg.execute(
        "INSERT INTO documents "
        "(id, user_id, title, source, doc_type, char_count, chunk_count, embed_model, created_at) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
        "ON CONFLICT (id) DO UPDATE SET "
        "user_id=$2, title=$3, source=$4, doc_type=$5, char_count=$6, "
        "chunk_count=$7, embed_model=$8, created_at=$9",
        meta["id"],
        meta.get("user_id") or "",
        meta["title"],
        meta["source"],
        meta["doc_type"],
        meta["char_count"],
        meta["chunk_count"],
        meta["embed_model"],
        meta["created_at"],
    )


async def insert_chunks(
    pg: asyncpg.Connection,
    chunks: list[StoredChunk],
    embeddings: np.ndarray,
    created_at: str,
) -> None:
    """批量写 chunk。embedding 存 pgvector 类型，用 list 传入。"""
    if not chunks:
        return

    rows: list[tuple[object, ...]] = []
    for chunk, vec in zip(chunks, embeddings):
        # NaN/Inf 会导致 pgvector 序列化出 0x00，必须在入库前拍平
        clean = np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32).tolist()
        rows.append(
            (
                _sanitize(chunk.id),
                _sanitize(chunk.doc_id),
                chunk.chunk_index,
                _sanitize(chunk.heading),
                _sanitize(chunk.content),
                _sanitize(chunk.raw),
                clean,
                _sanitize(" ".join(chunk.tokens)),
                created_at,
            )
        )

    await pg.executemany(
        "INSERT INTO chunks (id, doc_id, chunk_index, heading, content, raw, embedding, tokens, created_at) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
        "ON CONFLICT (id) DO NOTHING",
        rows,
    )


async def vector_search(
    pg: asyncpg.Connection,
    query_vec: np.ndarray,
    top_k: int = 50,
    *,
    user_id: str | None = "",
) -> list[StoredChunk]:
    """HNSW 索引的余弦相似度检索。

    pgvector 的 <=> 是余弦距离（1 - cosine），越小越近。
    这里先 L2 归一化 query_vec，保证和建库时的向量在同一空间。

    **隔离靠 JOIN 而不是查完再过滤**：先取 50 条再过滤，很可能一条都不剩
    （别人的文档占满了 top_k），表现为"我明明传了文档却检索不到"。
    """
    norm = np.linalg.norm(query_vec)
    if norm > 0:
        query_vec = query_vec / norm

    vec = query_vec.astype(np.float32).tolist()
    if user_id is None:
        rows = await pg.fetch(
            "SELECT c.id, c.doc_id, c.chunk_index, c.heading, c.content, c.raw, c.tokens "
            "FROM chunks c ORDER BY c.embedding <=> $1 LIMIT $2",
            vec,
            top_k,
        )
    else:
        rows = await pg.fetch(
            "SELECT c.id, c.doc_id, c.chunk_index, c.heading, c.content, c.raw, c.tokens "
            "FROM chunks c JOIN documents d ON d.id = c.doc_id "
            "WHERE d.user_id = $3 "
            "ORDER BY c.embedding <=> $1 LIMIT $2",
            vec,
            top_k,
            user_id,
        )
    return [_row_to_chunk(r) for r in rows]


async def load_all_tokens(
    pg: asyncpg.Connection,
    *,
    user_id: str | None = "",
) -> list[StoredChunk]:
    """读当前用户的全部 chunk（不含向量），用于构建 BM25 索引。

    每次检索都重建 BM25 索引是个已知的优化点：
    当前库 ≤ 1000 块时，重建耗时 <5ms，完全可接受。
    规模上去后再考虑内存缓存 + 增量更新。
    """
    if user_id is None:
        rows = await pg.fetch(
            "SELECT id, doc_id, chunk_index, heading, content, raw, tokens "
            "FROM chunks ORDER BY doc_id, chunk_index"
        )
    else:
        rows = await pg.fetch(
            "SELECT c.id, c.doc_id, c.chunk_index, c.heading, c.content, c.raw, c.tokens "
            "FROM chunks c JOIN documents d ON d.id = c.doc_id "
            "WHERE d.user_id = $1 ORDER BY c.doc_id, c.chunk_index",
            user_id,
        )
    return [_row_to_chunk(r) for r in rows]


async def delete_document(
    pg: asyncpg.Connection,
    doc_id: str,
    *,
    user_id: str | None = "",
) -> None:
    """级联删：chunks 表有 ON DELETE CASCADE，删 document 自动清理 chunk。

    doc_id 本身已经含 user 维度（见 ingest._doc_id），这里再带一次
    user_id 是纵深防御：万一以后有人改了 id 生成方式，越权删除仍被挡住。
    """
    if user_id is None:
        await pg.execute("DELETE FROM documents WHERE id = $1", doc_id)
    else:
        await pg.execute(
            "DELETE FROM documents WHERE id = $1 AND user_id = $2", doc_id, user_id
        )


async def list_all_documents(
    pg: asyncpg.Connection,
    *,
    user_id: str | None = "",
) -> list[dict[str, object]]:
    if user_id is None:
        rows = await pg.fetch("SELECT * FROM documents ORDER BY created_at DESC")
    else:
        rows = await pg.fetch(
            "SELECT * FROM documents WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
    return [dict(r) for r in rows]


async def list_document_chunks(
    pg: asyncpg.Connection,
    doc_id: str,
    limit: int = 20,
    offset: int = 0,
    *,
    user_id: str | None = "",
) -> list[StoredChunk]:
    """按顺序读某个文档的 chunk，用于前端预览。

    只取正文、不取 embedding：把 512 维向量拉到前端毫无意义，
    一个 500 块的文档会多传几 MB。
    """
    if user_id is None:
        rows = await pg.fetch(
            "SELECT id, doc_id, chunk_index, heading, content, raw, tokens "
            "FROM chunks WHERE doc_id = $1 ORDER BY chunk_index LIMIT $2 OFFSET $3",
            doc_id,
            limit,
            offset,
        )
    else:
        rows = await pg.fetch(
            "SELECT c.id, c.doc_id, c.chunk_index, c.heading, c.content, c.raw, c.tokens "
            "FROM chunks c JOIN documents d ON d.id = c.doc_id "
            "WHERE c.doc_id = $1 AND d.user_id = $4 "
            "ORDER BY c.chunk_index LIMIT $2 OFFSET $3",
            doc_id,
            limit,
            offset,
            user_id,
        )
    return [_row_to_chunk(r) for r in rows]


def _sanitize(text: str) -> str:
    """过滤 0x00 NULL 字节。PostgreSQL TEXT 列不接受这个字符。

    极少数文档（如从 PDF 或二进制源提取的文本）可能夹带 NULL，
    忽略它们比炸整次摄入合理得多。"""
    return text.replace("\x00", "")


def _row_to_chunk(row: asyncpg.Record) -> StoredChunk:
    return StoredChunk(
        id=row["id"],
        doc_id=row["doc_id"],
        chunk_index=row["chunk_index"],
        heading=row["heading"],
        content=row["content"],
        raw=row["raw"],
        tokens=row["tokens"].split() if row["tokens"] else [],
    )