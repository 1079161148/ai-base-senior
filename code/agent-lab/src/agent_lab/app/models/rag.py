"""RAG 数据模型（Pydantic）。

前端 / API 层的契约：后端内部用 dataclass（轻量），
对外的 JSON 用 Pydantic（FastAPI 自动校验 + 文档生成）。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChunkRef(BaseModel):
    """一条引用的原文来源。前端点一下能展开看整段。"""

    id: str
    doc_id: str
    doc_title: str = ""
    chunk_index: int
    heading: str
    raw: str  # 原文片段


class RAGResponse(BaseModel):
    """检索增强回答：答案 + 引用 + 检索统计。"""

    answer: str
    citations: list[ChunkRef] = Field(default_factory=list)
    retrieved_count: int = 0
    query_ms: float = 0.0


class RAGStats(BaseModel):
    """检索过程的性能统计（前端可以展示）"""

    query: str
    top_k: int
    duration_ms: float
    vector_hits: int
    keyword_hits: int
    merged_hits: int