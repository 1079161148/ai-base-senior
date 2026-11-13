"""asyncpg 连接池 + pgvector 初始化。

整个 S3 的向量存储都走这个池。和 SQLite 的 get_db() 平级 ——
待办继续用 SQLite，RAG 用 PostgreSQL，两套互不干扰。
"""

import logging
from collections.abc import AsyncGenerator

import asyncpg
from pgvector.asyncpg import register_vector

from .config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def _setup_conn(conn: asyncpg.Connection) -> None:
    """每根新连接建立时注册 pgvector 编解码器。

    必须挂在 create_pool 的 setup 回调上，而不是借一根连接注册完还回去。
    codec 是挂在**连接对象**上的，池里其他连接不会继承 ——
    之前那样写，只有被借出的那一根能传/收向量，
    换个连接就抛 `DataError: expected str, got list`（list 被当 text 编码）。
    """
    try:
        # 先确保扩展存在：register_vector 依赖库里的 vector 类型，
        # 池可能在 init_pg() 建表之前就建立连接，不兜底会注册失败。
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await register_vector(conn)
    except Exception:
        # 注册失败不要让建连跟着炸，否则整个服务起不来
        logger.warning("pgvector codec 注册失败（向量类型暂不可用）", exc_info=True)


async def create_pool() -> asyncpg.Pool:
    """启动时调一次，创建进程级连接池。"""
    global _pool

    pool = await asyncpg.create_pool(
        dsn=settings.PG_DSN,
        min_size=settings.PG_MIN_SIZE,
        max_size=settings.PG_MAX_SIZE,
        setup=_setup_conn,
    )
    _pool = pool
    logger.info("pgvector 连接池已创建 (min=%d max=%d)", settings.PG_MIN_SIZE, settings.PG_MAX_SIZE)
    return pool


async def close_pool() -> None:
    """关闭时调一次。"""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("pgvector 连接池已关闭")


async def init_pg() -> None:
    """建表 + HNSW 索引。幂等，反复调不会报错。"""
    pool = _pool
    if pool is None:
        raise RuntimeError("pg pool 尚未创建，请先调 create_pool()")

    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id          TEXT PRIMARY KEY,
                -- S9：归属用户。空串是 S9 之前的老数据，
                -- 由启动时的 claim_legacy_pg 统一划给演示账号。
                user_id     TEXT    NOT NULL DEFAULT '',
                title       TEXT    NOT NULL,
                source      TEXT    NOT NULL,
                doc_type    TEXT    NOT NULL,
                char_count  INTEGER NOT NULL,
                chunk_count INTEGER NOT NULL,
                embed_model TEXT    NOT NULL,
                created_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id          TEXT PRIMARY KEY,
                doc_id      TEXT    NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                heading     TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                raw         TEXT    NOT NULL,
                embedding   vector(512) NOT NULL,
                tokens      TEXT    NOT NULL,
                created_at  TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);

            -- S4：长期记忆。存用户偏好、事实、决定，用向量检索匹配当前上下文。
            CREATE TABLE IF NOT EXISTS long_term_memories (
                id          SERIAL PRIMARY KEY,
                session_id  TEXT    NOT NULL,
                key_text    TEXT    NOT NULL,    -- 记忆的简短标识
                content     TEXT    NOT NULL,    -- 完整记忆文本
                embedding   vector(512) NOT NULL,
                source_role TEXT    NOT NULL,    -- 'user' 或 'assistant'，知道谁说的
                importance  REAL    NOT NULL DEFAULT 0.5,  -- 重要性权重 [0,1]
                created_at  TEXT    NOT NULL
            );
        """)

        # S9：老库补列。PG 比 SQLite 友好，ADD COLUMN IF NOT EXISTS 直接支持，
        # 不需要先查 information_schema。幂等，每次启动都能跑。
        await conn.execute(
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT ''"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id)"
        )

        # HNSW 索引：余弦距离，m=16 ef_construction=64 是 pgvector 的默认参数，
        # 对 100k 以下量级完全够用，不用调。
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_embed "
            "ON chunks USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ltm_embed "
            "ON long_term_memories USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )

    logger.info("pgvector 表与索引已就绪")


async def get_pg() -> asyncpg.Connection:
    """从池里取一个连接（一般不直接调用，通过 FastAPI 依赖注入）。

    FastAPI Depends 可以这样写：
        async def get_pg_conn() -> asyncpg.Connection:
            async with _pool.acquire() as conn:
                yield conn
    """
    pool = _pool
    if pool is None:
        raise RuntimeError("pg pool 尚未创建")
    return await pool.acquire()


_pool_for_fastapi: asyncpg.Pool | None = None


def get_pool() -> asyncpg.Pool | None:
    """取当前连接池，可能为 None。

    给脚本和后台任务用（它们在请求上下文之外，拿不到 Depends）。
    没有池时返回 None 而不是抛异常，调用方自己决定是报错还是跳过。
    """
    return _pool or _pool_for_fastapi


def set_pool(pool: asyncpg.Pool) -> None:
    """让 lifespan 把池注册进来，FastAPI 依赖注入才能拿到。"""
    global _pool_for_fastapi
    _pool_for_fastapi = pool


async def get_pg_fastapi() -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI 依赖注入用：每个请求从池里借一个连接，结束后自动还。

    在 API 路由里这样用：
        @router.get("/xxx")
        async def xxx(pg: asyncpg.Connection = Depends(get_pg_fastapi)):
            ...
    """
    if _pool_for_fastapi is None:
        raise RuntimeError("pg pool 尚未创建")
    async with _pool_for_fastapi.acquire() as conn:
        yield conn