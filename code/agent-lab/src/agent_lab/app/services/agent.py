"""Agent 主循环（S2）。

一句话差别：**S1 让模型会说话，S2 让模型能动手。**

    user → [模型] ──要调工具?── 否 ──> 输出答案，结束
                     │
                     是
                     ↓
                 执行工具（真的读写数据库）
                     ↓
                 结果塞回对话 → 再问模型 ──┐
                     ↑                      │
                     └──────────────────────┘

**为什么必须循环，而不是一次调用**：
模型本身没有执行能力，它只会"说"「我要调 create_todo，参数是 {...}」。
真正写入数据库的是我们。写完还得把结果告诉它，它才知道成功了没有 ——
所以至少两轮请求：第一轮拿到工具请求，第二轮拿到最终回答。

**三重刹车**（缺一个都可能变成烧钱机器）：
  1. 步数上限  —— 模型可能反复调工具停不下来
  2. 成本上限  —— 步数够用但每步都很贵时，步数刹车拦不住
  3. 工具超时  —— 单个工具卡死不能拖住整轮对话
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from dataclasses import asdict

import aiosqlite
import httpx

from ..core.config import settings
from . import llm, metrics, tools
from . import trace as trace_service

logger = logging.getLogger(__name__)

# 计划要求 10 步。每步是一次完整的模型请求，按 token 计费，
# 所以步数刹车必须和成本刹车同时存在 —— 光有步数，10 步也可能很贵。
MAX_STEPS = 10

SYSTEM_PROMPT = """你是 agent-lab 的待办与文档助手，可以读写用户的待办清单，也可以检索已上传的文档。

严格遵守以下规则：

1. **涉及待办的内容、数量、完成状态时，必须先调用 list_todos 查真实数据**。
   你看不到数据库，任何凭上下文推测的答案都是编造的。
2. **涉及知识库里的文档、技术规范、概念解释时，必须先调用 search_docs 检索**。
   你看不到文档内容，任何凭上下文推测的答案都是编造的。
3. 用户要求新增、修改、删除待办时，直接调用对应工具完成，再用一两句话说明结果。
4. 工具返回里带 error 时，如实告诉用户失败原因，**不要谎称成功**。
5. 回答涉及文档内容时，要注明来源（如「根据《RAG完整链路》第 3.5 节…」）。
6. 删除操作只在用户明确要求时执行。
7. 用简体中文回答，简洁直接，不啰嗦。"""

# ---- S7：版本指纹 ----
# 提示词/工具定义一改，版本号自动变（内容哈希），不需要人记得手动升版本。
PROMPT_VERSION = trace_service.sha_short(SYSTEM_PROMPT)
TOOL_VERSION = trace_service.sha_short(
    json.dumps(tools.TOOLS, ensure_ascii=False, sort_keys=True)
)


def _int(value: object) -> int:
    return value if isinstance(value, int) else 0


def _last_user_message(messages: Sequence[llm.Message]) -> str:
    """取最后一条 user 消息。前面的是历史，对复盘"这次问了什么"没意义。"""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                return content
    return ""


async def run(
    messages: Sequence[llm.Message],
    *,
    client: httpx.AsyncClient,
    db: aiosqlite.Connection,
    is_disconnected: Callable[[], Awaitable[bool]],
    session_id: str | None = None,
    user_id: str = "",
) -> AsyncGenerator[dict[str, object], None]:
    """驱动一次完整对话，逐帧产出前端要的事件。

    产出的事件（与 chat.py 的 SSE 帧一一对应）：
        {"reasoning": "..."}   思考增量
        {"delta": "..."}       答案增量
        {"tool": {...}}        工具调用状态
        {"done": true, ...}    结束帧（含 token / 成本 / trace）
    """
    started = time.perf_counter()

    # 历史是这一轮对话的"工作内存"，每次工具往返都往里面追加，
    # 模型下一轮才能看到"我刚才调了什么、结果是什么"
    history: list[llm.Message] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *messages,
    ]

    record = trace_service.Trace(
        trace_id=trace_service.new_id(),
        started_at=trace_service.now_iso(),
        model=settings.LLM_MODEL,
        question=trace_service.clip(_last_user_message(messages)),
        session_id=session_id,
        user_id=user_id,
        prompt_version=PROMPT_VERSION,
        tool_version=TOOL_VERSION,
        config_fingerprint=trace_service.fingerprint(
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            prompt_version=PROMPT_VERSION,
            tool_version=TOOL_VERSION,
        ),
    )

    total_chars = 0
    total_reasoning = 0
    prompt_tokens = 0
    completion_tokens = 0
    tool_calls_total = 0
    stopped_reason = "completed"

    for step in range(MAX_STEPS + 1):
        # 最后一轮不再提供工具：逼模型用现有信息作答，避免无限调用
        last_round = step == MAX_STEPS
        if last_round:
            logger.info("达到步数上限（%s），强制收尾", MAX_STEPS)

        if await is_disconnected():
            logger.info("客户端已断开，停止生成")
            stopped_reason = "disconnected"
            break

        step_started = time.perf_counter()
        prompt_before = prompt_tokens
        completion_before = completion_tokens

        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: list[llm.ToolCall] = []

        async for chunk in llm.stream_chat(
            history,
            client=client,
            tools=None if last_round else tools.TOOLS,
        ):
            if chunk.reasoning:
                reasoning_parts.append(chunk.reasoning)
                total_reasoning += len(chunk.reasoning)
                yield {"reasoning": chunk.reasoning}

            if chunk.delta:
                text_parts.append(chunk.delta)
                total_chars += len(chunk.delta)
                yield {"delta": chunk.delta}

            if chunk.tool_calls:
                tool_calls = chunk.tool_calls

            # usage 只在流的最后一帧出现（choices 为空数组），
            # 所以是"按需累加"而不是"每帧相加"。
            if chunk.usage:
                prompt_tokens += _int(chunk.usage.get("prompt_tokens"))
                completion_tokens += _int(chunk.usage.get("completion_tokens"))

        # 先落一条 step 记录（此时还不知道工具有没有、结果是什么）。
        # 提前塞进 record.steps 的好处：后面即使因超支 break，
        # 这一步也不会在 trace 里凭空消失。
        step_record = trace_service.StepRecord(
            step=step,
            model_output=trace_service.clip("".join(text_parts)),
            reasoning=trace_service.clip("".join(reasoning_parts)),
            prompt_tokens=prompt_tokens - prompt_before,
            completion_tokens=completion_tokens - completion_before,
            duration_ms=round((time.perf_counter() - step_started) * 1000, 1),
        )
        record.steps.append(step_record)

        # 成本刹车：这一轮已经花了钱，先算账再决定要不要继续。
        # 放在工具执行之前 —— 超支了就不该再往下走，哪怕工具本身不花钱。
        cost = settings.cost_of(prompt_tokens, completion_tokens)
        if cost >= settings.LLM_MAX_COST_CNY:
            stopped_reason = "cost_limit"
            logger.warning("达到成本上限：%.4f 元 ≥ %.4f 元", cost, settings.LLM_MAX_COST_CNY)
            yield {
                "delta": f"\n\n（本次请求已花费 ¥{cost:.4f}，达到单次上限 "
                f"¥{settings.LLM_MAX_COST_CNY}，已停止继续调用模型）"
            }
            break

        if not tool_calls:
            # 模型这一轮直接给了答案，对话结束
            stopped_reason = "max_steps" if last_round else "completed"
            break

        tool_calls_total += len(tool_calls)

        # 必须把 assistant 的"工具请求"原样记进历史。
        # 少了这条，下一次请求里 tool 消息的 tool_call_id 就找不到对应请求，
        # 上游会直接返回 400 invalid_request_error。
        history.append(
            {
                "role": "assistant",
                # 有正文就带上（模型可能"我先看看"然后调工具），没正文要给 None 而不是 ""
                "content": "".join(text_parts) or None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": call.arguments},
                    }
                    for call in tool_calls
                ],
            }
        )

        for call in tool_calls:
            # 先发"开始"帧：工具执行通常几毫秒，但网络慢或库锁住时可能久，
            # 前端能立刻显示"正在调用 xxx"，而不是干等。
            parsed_args = _safe_parse(call.arguments)
            yield {
                "tool": {
                    "id": call.id,
                    "name": call.name,
                    "arguments": parsed_args,
                    "status": "running",
                }
            }

            tool_started = time.perf_counter()

            # 工具超时刹车：用 wait_for 而不是在每个工具内部传 timeout ——
            # 这样任何工具（含以后接的 HTTP API）都自动受保护，
            # 不需要每个实现各自记得处理。
            try:
                raw = await asyncio.wait_for(
                    # user_text 传给护栏：判断"删除"是不是用户真的要求过
                    tools.execute(
                        db,
                        call.name,
                        call.arguments,
                        _last_user_message(messages),
                        user_id=user_id,
                    ),
                    timeout=settings.TOOL_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                logger.warning("工具 %s 超时（>%.0fs）", call.name, settings.TOOL_TIMEOUT_SECONDS)
                raw = json.dumps(
                    {"error": f"工具执行超时（超过 {settings.TOOL_TIMEOUT_SECONDS:.0f} 秒）"},
                    ensure_ascii=False,
                )

            tool_ms = round((time.perf_counter() - tool_started) * 1000, 1)
            result = _safe_parse(raw)
            failed = _has_error(result)

            history.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": raw,
                }
            )

            # 追加到本步记录里。step_record 是同一个对象引用，
            # 上面已经 append 进 record.steps，这里改它即可生效。
            step_record.tool_calls.append(
                trace_service.ToolRecord(
                    name=call.name,
                    arguments=parsed_args,
                    result=result,
                    status="error" if failed else "done",
                    duration_ms=tool_ms,
                )
            )

            yield {
                "tool": {
                    "id": call.id,
                    "name": call.name,
                    "arguments": parsed_args,
                    "status": "error" if failed else "done",
                    "result": result,
                    "duration_ms": tool_ms,
                }
            }

    total_tokens = prompt_tokens + completion_tokens
    final_cost = settings.cost_of(prompt_tokens, completion_tokens)

    record.duration_ms = round((time.perf_counter() - started) * 1000, 1)
    record.stopped_reason = stopped_reason
    record.usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_cny": round(final_cost, 6),
        "tool_calls": tool_calls_total,
    }

    try:
        await trace_service.save(record)
    except OSError:
        # trace 写不进去绝不能影响用户拿到回答 —— 它是旁路，不是主链路
        logger.exception("保存 trace 失败：%s", record.trace_id)

    # 同时落一行标量指标：JSON 用来回放，这张表用来聚合（看板/CI 门禁）
    await metrics.record(db, record)

    logger.info(
        "对话结束：%s 字、%s 字思考、%s 次工具、%s token、¥%.6f（%s）trace=%s",
        total_chars,
        total_reasoning,
        tool_calls_total,
        total_tokens,
        final_cost,
        stopped_reason,
        record.trace_id,
    )

    yield {
        "done": True,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            # 保留 6 位小数：一次普通对话只有千分之几元，
            # 四舍五入到 2 位会全变成 0.00，看不出到底花了多少
            "cost_cny": round(final_cost, 6),
            "chars": total_chars,
            "reasoning_chars": total_reasoning,
            "tool_calls": tool_calls_total,
            "stopped_reason": stopped_reason,
        },
        "trace_id": record.trace_id,
        # 完整 trace 直接随结束帧下发：前端渲染时间线不必再发一次请求，
        # 也避免"刚结束就去读文件"的时序问题（文件可能还在写）。
        "trace": asdict(record),
    }


def _safe_parse(raw: str) -> object:
    """把工具返回的 JSON 字符串转成对象给前端。

    解析失败就原样返回字符串 —— 展示层出问题，远不如把原文亮出来有用。
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _has_error(result: object) -> bool:
    return isinstance(result, dict) and "error" in result
