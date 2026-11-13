"""本地嵌入：把文本变成向量。

**为什么用本地模型而不是调 API**：
这个中转站的 bge-m3 需要单独订购（返回 402），其他嵌入模型 404。
本地 bge-small-zh 512 维，CPU 上一次编码几百条 chunk 只需一两秒，
而且零成本、不依赖网络 —— 对学习项目比云端更稳。

**三条硬规则**（教材 4.2）：
  1. 建库和查询必须用同一个模型 —— 所以模型名写进 documents 表
  2. 换模型必须重建索引
  3. query 和 passage 用不同前缀（bge 系列的约定）
"""

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from ...core.config import settings

# fastembed **不能**在模块级导入。
# 它一被导入就会连带导入 huggingface_hub，而后者在导入瞬间就把
# HF_ENDPOINT 固化下来。config.py 里设的镜像地址必须先生效，
# 所以只在真正要加载模型时才 import（见 _model）。
if TYPE_CHECKING:
    from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
# bge 系列要求：查询前加这段指令，passage 不加。
# 不加的话，"超时时间" 和 "接口超时设置为 3 秒" 的相似度会明显下降 ——
# 因为同一个词在 query 和 doc 里应该处于不同的语义空间，指令告诉模型用查询空间编码。
_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


@lru_cache(maxsize=1)
def _model() -> "TextEmbedding":
    """模型是进程级单例：加载一次约 1s，之后每次编码不需要重新加载。

    缓存目录显式指定为项目 data/models，不用 fastembed 默认的
    %TEMP%/fastembed_cache —— 那里会被磁盘清理和重启干掉，
    下次启动就得重新下载几百 MB。
    """
    from fastembed import TextEmbedding

    cache_dir = Path(settings.MODEL_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)

    logger.info("加载嵌入模型 %s（缓存目录 %s）…", _MODEL_NAME, cache_dir)
    return TextEmbedding(model_name=_MODEL_NAME, cache_dir=str(cache_dir))


def model_info() -> dict[str, object]:
    """入库时会记下这个，以后换模型能第一时间发现。"""
    return {"name": _MODEL_NAME, "dim": 512, "backend": "fastembed/onnx"}


def _encode(texts: list[str]) -> np.ndarray:
    """同步编码：CPU is CPU，tonumpy 是中文字符，算的。"""
    if not texts:
        return np.empty((0, 512), dtype=np.float32)

    vectors = list(_model().embed(texts))
    arr = np.asarray(vectors, dtype=np.float32)

    # NaN / Inf 会污染 pgvector 索引，替换为零
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

    # 归一化后点积就是余弦相似度，检索时省掉每次除模
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


async def embed_passages(texts: list[str]) -> np.ndarray:
    """文档入库时的批量编码。阻塞操作，必须跑在 to_thread 里。"""
    return await asyncio.to_thread(_encode, texts)


async def embed_query(text: str) -> np.ndarray:
    """单条查询。加 bge 指令前缀后编码。"""
    logger.debug("嵌入查询: %s …", text[:40])
    queries: list[str] = [_QUERY_INSTRUCTION + text]
    vecs = await asyncio.to_thread(_encode, queries)
    return vecs[0]


def warm_up() -> None:
    """进程启动时预热：首次调用加载模型，之后不会再等。

    放在 lifespan 里：启动慢 1s，比第一个用户干等 1s 要好 100 倍。
    加载失败不打日志也不崩溃 —— 只是 RAG 功能不可用，其余接口正常。
    """
    try:
        _model()
        _encode(["测试"])
        logger.info("嵌入模型预热完成 %s", _MODEL_NAME)
    except OSError:
        # 下载失败最常见的两个原因，直接写出来，省得去猜：
        #   1. 连不上 HuggingFace（国内常态），改 HF_ENDPOINT 走镜像
        #   2. 模型缓存目录不可写（权限 / 磁盘满）
        logger.warning(
            "嵌入模型预热失败，RAG 检索将不可用。"
            "排查：确认 HF_ENDPOINT=%s 可访问，缓存目录 %s 可写",
            settings.HF_ENDPOINT or "https://huggingface.co",
            settings.MODEL_CACHE_DIR,
        )
    except Exception:  # noqa: BLE001
        logger.exception("嵌入模型预热异常")