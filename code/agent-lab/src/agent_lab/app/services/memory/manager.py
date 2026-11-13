"""S4 · 记忆管理器 —— 三层记忆的编排者。

职责：
    1. 加载：从数据库读出工作记忆 + 摘要记忆 + 长期记忆
    2. 组装：按 ContextBudget 拼接成最终 prompt
    3. 压缩：工作记忆超阈值时自动调用 LLM 生成摘要
    4. 写入：从对话中提取关键信息存入长期记忆

三层记忆：
    L0 工作记忆 — 最近 N 轮原文，直接在内存里
    L1 摘要记忆 — 更早轮次的压缩版，存在 SQLite
    L2 长期记忆 — 用户偏好/事实，向量检索，存在 pgvector
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import aiosqlite
import asyncpg

from ...core.config import settings
from .. import llm
from ..rag import embedder
from . import budget as budget_mod
from . import session as session_svc

logger = logging.getLogger(__name__)


@dataclass
class MemoryContext:
    """组装后的上下文 + 使用统计。"""

    messages: list[llm.Message]  # 完整的 messages 列表发给 agent
    usage: dict                  # 上下文预算使用情况


# ---- 公开 API ----

async def load_context(
    *,
    session_id: str,
    db: aiosqlite.Connection,
    pg: asyncpg.Connection,
    new_user_message: str,
) -> MemoryContext:
    """加载会话的完整上下文（三层记忆 + 当前消息 + token 预算）。

    这是 S4 的入口函数，chat.py 在每次对话时调用。
    """
    ctx = budget_mod.ContextBudget()

    # ① 系统提示（priority 0，绝不裁剪）
    from ..agent import SYSTEM_PROMPT

    ctx.add("system", SYSTEM_PROMPT, priority=0)

    # ② 长期记忆（priority 3，比工作记忆优先保留）
    ltm_text = await _load_long_term(pg, new_user_message)
    if ltm_text:
        ctx.add("long_term", ltm_text, priority=3)

    # ③ 摘要记忆（priority 3）
    memories = await session_svc.load_memories(db, session_id)
    if memories:
        summary = "\n".join(
            f"[早期对话摘要 #{i + 1}]: {m['content']}"
            for i, m in enumerate(memories)
        )
        ctx.add("summary", summary, priority=3)

    # ④ 工作记忆（原始消息，priority 4 —— 是最先被裁的）
    raw_msgs = await session_svc.get_session_messages(db, session_id)
    working_limit = settings.WORKING_MEMORY_ROUNDS * 2  # 每轮 = user + assistant
    if len(raw_msgs) > working_limit:
        working_msgs = raw_msgs[-working_limit:]
        logger.info(
            "工作记忆窗口：只取最近 %d/%d 条", working_limit, len(raw_msgs)
        )
    else:
        working_msgs = raw_msgs

    for r in working_msgs:
        role = r["role"]
        if role in ("system", "tool"):
            continue  # system 已单独处理；tool 不进上下文（见 _build_messages）
        content = r.get("content") or ""
        ctx.add(f"msg_{role}", f"[{role}]: {content}", priority=4)

    # ⑤ 当前用户消息（priority 1，第二重要的，仅次于 system）
    ctx.add("current_question", f"[user]: {new_user_message}", priority=1)

    # 预算检查 + 裁剪
    if ctx.is_over():
        ctx.trim()

    # 组装成 agent.py 需要的 messages 格式
    messages = _build_messages(
        system_prompt=SYSTEM_PROMPT,
        ltm_text=ltm_text,
        memory_texts=[m["content"] for m in memories] if memories else [],
        working_msgs=working_msgs,
        new_msg=new_user_message,
    )

    return MemoryContext(messages=messages, usage=ctx.get_usage())


async def compress_working_memory(
    *,
    session_id: str,
    db: aiosqlite.Connection,
    client: object,  # httpx.AsyncClient
) -> int:
    """检查工作记忆是否超阈值，超了就生成摘要并清理。

    裁剪策略：
        1. 数一下工作记忆占用
        2. 只保留最近 WORKING_MEMORY_ROUNDS 轮
        3. 超过的那部分用 LLM 生成一段摘要
        4. 摘要存到 session_memories
        5. 删掉对应消息
    """
    msgs = await session_svc.get_session_messages(db, session_id)
    if not msgs:
        return 0

    round_count = _count_rounds(msgs)
    if round_count <= settings.WORKING_MEMORY_ROUNDS:
        return 0  # 没超标，不压缩

    # 计算切割线：保留最近 N 轮
    keep_msgs = _find_cutoff(msgs, settings.WORKING_MEMORY_ROUNDS)
    if not keep_msgs or keep_msgs[0]["id"] == msgs[0]["id"]:
        return 0  # 没有旧消息可压缩

    # 提取要被压缩的消息
    cut_id = keep_msgs[0]["id"]
    old_msgs = [m for m in msgs if m["id"] < cut_id]
    # 保留的消息（含切断线的第一条）
    remain_msgs = [m for m in msgs if m["id"] >= cut_id]

    # 用 LLM 生成摘要
    summary = await _generate_summary(client, old_msgs)
    if not summary:
        return 0

    token_count = budget_mod.count_tokens(summary)

    # 存摘要
    await session_svc.save_memory(
        db, session_id,
        msg_start=old_msgs[0]["id"],
        msg_end=cut_id,
        content=summary,
        token_count=token_count,
    )

    # 删旧消息
    await session_svc.delete_messages_from(db, session_id, cut_id)

    logger.info(
        "压缩了 %d 条消息 → %d token 摘要（保留 %d 条）",
        len(old_msgs), token_count, len(remain_msgs),
    )
    return token_count


async def write_long_term_memory(
    *,
    session_id: str,
    pg: asyncpg.Connection,
    user_msg: str,
    assistant_reply: str,
) -> None:
    """从一轮对话中提取关键信息存入长期记忆（pgvector）。

    策略：
        只存 user 消息和 assistant 最终回答 —— 不存中间的工具调用杂音。
        用嵌入向量建索引，未来对话时按语义相似度检索。
    """
    from ..rag.store import _sanitize

    # 合并 user + assistant 作为记忆原文
    memory_text = f"用户说：{user_msg}\n助手回答：{assistant_reply[:500]}"

    # 生成嵌入
    vec = await embedder.embed_query(memory_text)

    # 写入 pgvector
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    await pg.execute(
        """INSERT INTO long_term_memories
           (session_id, key_text, content, embedding, source_role, importance, created_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7)""",
        _sanitize(session_id),
        _sanitize(user_msg[:100]),
        _sanitize(memory_text),
        vec.astype("float32").tolist(),
        "user",
        0.5,
        now,
    )

    logger.debug("长期记忆已写入：%.100s…", user_msg)


# ---- 内部函数 ----

def _build_messages(
    *,
    system_prompt: str,
    ltm_text: str,
    memory_texts: list[str],
    working_msgs: list[dict],
    new_msg: str,
) -> list[llm.Message]:
    """把各层记忆拼接成 agent.py 需要的 messages 格式。

    结构：
        [system]  (角色 + 规则 + 长期记忆 + 摘要记忆)
        [user]    历史消息（跳过 system 角色）
        [assistant] 历史回复
        [user]    当前问题
    """
    # 正文放 system prompt 之后、当前问题之前
    system_parts = [system_prompt]
    if ltm_text:
        system_parts.append(f"\n[长期记忆 — 用户偏好与事实]\n{ltm_text}")
    if memory_texts:
        summary = "\n".join(
            f"[摘要 #{i + 1}]: {t}" for i, t in enumerate(memory_texts)
        )
        system_parts.append(f"\n[对话历史摘要]\n{summary}")

    messages: list[llm.Message] = [
        {"role": "system", "content": "\n\n".join(system_parts)}
    ]

    # 加了 system / ltm / summary 后，历史消息不再需要 system
    for r in working_msgs:
        role = r["role"]
        if role in ("system", "tool"):
            # tool 消息绝对不能原样塞回上下文：
            # OpenAI 协议要求 role=tool 必须紧随一条 tool_calls 里包含该 id 的
            # assistant 消息，否则整轮请求直接 400
            # （tool_call_id does not match a preceding assistant tool call）。
            # 我们存 assistant 时没有保留 tool_calls，无法正确配对，因此丢弃。
            # 工具结果的实际内容已经体现在紧随其后的 assistant 正文里。
            continue
        messages.append({
            "role": role,
            "content": r.get("content") or "",
        })

    # 当前问题
    messages.append({"role": "user", "content": new_msg})

    return messages


async def _load_long_term(
    pg: asyncpg.Connection,
    query: str,
) -> str:
    """用当前问题检索最相关的长期记忆。"""
    qv = await embedder.embed_query(query)

    rows = await pg.fetch(
        """SELECT content, 1 - (embedding <=> $1) AS sim
           FROM long_term_memories
           WHERE 1 - (embedding <=> $1) > $2
           ORDER BY embedding <=> $1
           LIMIT $3""",
        qv.astype("float32").tolist(),
        settings.LONG_TERM_MIN_SCORE,
        settings.LONG_TERM_TOP_K,
    )

    if not rows:
        return ""

    return "\n".join(
        f"[相关记忆 — 相似度 {r['sim']:.2f}]: {r['content']}"
        for r in rows
    )


async def _generate_summary(
    client: object,  # httpx.AsyncClient
    messages: list[dict],
) -> str:
    """用 LLM 把一堆旧消息压缩成一段摘要。"""
    if not messages:
        return ""

    dialogue = "\n".join(
        f"[{m['role']}]: {m.get('content', '') or '[工具调用]'}"
        for m in messages
    )

    prompt = (
        "请把以下对话记录压缩成一段中文摘要。\n"
        "**必须保留**：数字、人名、日期、决定、偏好。\n"
        "**省略**：客套话、重复内容、工具调用的技术细节。\n"
        "只输出摘要，不要加「摘要：」等前缀。\n\n"
        f"{dialogue}"
    )

    payload = {
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 400,
        "temperature": 0.2,
    }

    try:
        import httpx as httpx_mod

        http_client: httpx_mod.AsyncClient = client  # type: ignore[annotation-type-mismatch]
        resp = await http_client.post(
            f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        logger.exception("生成摘要失败")
        return ""


def _count_rounds(messages: list[dict]) -> int:
    """数一下有多少轮 user 提问。"""
    return sum(1 for m in messages if m["role"] == "user")


def _find_cutoff(
    messages: list[dict],
    keep_rounds: int,
) -> list[dict]:
    """从后往前数 keep_rounds 轮 user 消息，返回应保留的消息。

    切割点在最后一轮"被保留"的 user 消息处。
    """
    count = 0
    for i in range(len(messages) - 1, -1, -1):
        if messages[i]["role"] == "user":
            count += 1
            if count == keep_rounds:
                return messages[i:]
    return messages  # 不够 N 轮，全保留