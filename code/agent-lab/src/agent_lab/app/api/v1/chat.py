"""对话接口（S1 直连模型 → S2 接入工具调用 → S4 会话记忆）。

和 `demo.py` 的唯一区别是：那里 yield 的是假字符串，这里 yield 的是真实增量。
**SSE 的外壳从头到尾没变** —— 这正是 S0 先做假流的价值：
协议稳定了，底层从"假数据"换成"模型"再换成"模型 + 工具"+ "记忆"，前端几乎不用动。
"""

import logging
from collections.abc import AsyncGenerator
from typing import Annotated, cast

import aiosqlite
import asyncpg
import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ...core.config import settings
from ...core.db import get_db
from ...core.errors import ApiError
from ...core.pg import get_pg_fastapi
from ...core.security import CurrentUserDep
from ...core.sse import encode as sse
from ...models.chat import ChatRequest
from ...models.session import ChatRequestV2
from ...services import agent, guard, llm
from ...services.memory import manager as mem_mgr
from ...services.memory import session as session_svc
from ...services.ratelimit import concurrency, ensure_daily_budget, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

DbDep = Annotated[aiosqlite.Connection, Depends(get_db)]
PgDep = Annotated[asyncpg.Connection, Depends(get_pg_fastapi)]


def _harden_system(messages: list[dict[str, object]], hint: str) -> None:
    """把安全提示追加到 system，没有 system 就插一条。

    注意是**追加**而不是替换：原有的角色设定必须保留，
    否则加固提示会把"你是待办助手"冲掉，问题更大。
    """
    for m in messages:
        if m.get("role") == "system":
            m["content"] = f"{m.get('content') or ''}{hint}"
            return
    messages.insert(0, {"role": "system", "content": hint.strip()})


@router.post(
    "/stream",
    summary="流式对话（含工具调用）",
    description=(
        "以 Server-Sent Events 返回模型的逐字输出，以及工具调用过程。\n\n"
        "帧格式：\n"
        '- `{"reasoning": "思考"}` —— 推理模型的思考增量（普通模型不会出现）\n'
        '- `{"delta": "文字"}` —— 答案正文的增量\n'
        '- `{"tool": {"id", "name", "arguments", "status", "result"}}` —— 工具调用\n'
        "  - `status=running` 表示开始执行，此时没有 `result`\n"
        "  - `status=done` / `status=error` 表示结束，带 `result`\n"
        '- `{"done": true, "usage": {...}}` —— 正常结束\n'
        '- `{"error": {"code": "...", "message": "..."}}` —— 中途出错（此时 HTTP 状态码仍是 200）'
    ),
    response_class=StreamingResponse,
)
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    user: CurrentUserDep,
    db: DbDep,
) -> StreamingResponse:
    # 前置检查放在返回 StreamingResponse **之前**：
    # 一旦开始推送，响应头（200）就发出去了，再想改成 503 是不可能的。
    # 所以"配置缺失"这种能提前判定的错误，必须在这里就拦下。
    if not settings.llm_configured:
        raise ApiError(
            503,
            "LLM_NOT_CONFIGURED",
            "还没有配置模型：请在 agent-lab/.env 里填写 LLM_API_KEY（LLM_BASE_URL / LLM_MODEL 可选）",
        )

    # 连接由 lifespan 创建、进程内复用 —— 每次请求新建 AsyncClient
    # 会丢掉连接池，TLS 握手要重来一遍，首字节延迟明显变长。
    client = cast(httpx.AsyncClient, request.app.state.http)

    # 转成 dict 交给 agent 层：工具调用会产生 ChatMessage 表达不了的消息形态
    # （assistant 带 tool_calls、role="tool"），见 services/llm.py 里的说明。
    messages: list[llm.Message] = [m.model_dump() for m in payload.messages]

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # token / 成本 / 停止原因这些统计已经在 agent 里算完，
            # 随 done 帧一起下发。这一层只负责编码成 SSE ——
            # 两处各算一遍，迟早会算出两个不一样的数。
            async for event in agent.run(
                messages,
                client=client,
                db=db,
                is_disconnected=request.is_disconnected,
                user_id=user.id,
            ):
                yield sse(event)

        except ApiError as exc:
            # 这里抛出的错误（401 / 402 / 超时）发生在流已经 200 之后，
            # 改不了状态码，只能发一条 error 帧让前端自己中断。
            yield sse({"error": {"code": exc.code, "message": exc.message}})

        except Exception as exc:  # noqa: BLE001 - 生成器里必须兜底，否则连接会静默挂着
            # 注意：asyncio.CancelledError 继承自 BaseException 而不是 Exception，
            # 客户端断开时的取消不会被这里吞掉，会正常向上传播。
            logger.exception("对话流异常: %s", exc)
            yield sse({"error": {"code": "INTERNAL_ERROR", "message": "生成过程中出错，请重试"}})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # 和 demo 一样：关掉 Nginx 一类反向代理的响应缓冲，
            # 否则前端会"沉默十几秒后一次性收到全文"，流式就白做了
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/stream-v2",
    summary="流式对话（带会话记忆与上下文预算）",
    response_class=StreamingResponse,
)
async def chat_stream_v2(
    payload: ChatRequestV2,
    request: Request,
    user: CurrentUserDep,
    db: DbDep,
    pg: PgDep,
) -> StreamingResponse:
    """S4 版对话：自动管理三层记忆 + 上下文预算。

    前端只需传 session_id + content，历史由服务端维护。
    若无 session_id 则自动创建新会话。
    """
    if not settings.llm_configured:
        raise ApiError(503, "LLM_NOT_CONFIGURED", "还没有配置模型")

    # ---- S8 护栏：全部拦在"建会话/调模型"之前 ----
    # 顺序是有讲究的：**限流必须最先**。
    # 放在内容检查之后的话，"刷接口"的请求虽然被 400 挡下，
    # 但每次都要跑一遍正则 + 查库，量大时同样是拒绝服务；
    # 而且攻击者用合法请求就能绕过配额统计。
    ip = request.client.host if request.client else "unknown"
    allowed, retry_after = limiter.allow(ip)
    if not allowed:
        raise ApiError(
            429, "RATE_LIMITED", f"请求过于频繁，请 {retry_after:.0f} 秒后再试"
        )
    limiter.prune()

    verdict = guard.check_input(payload.content)
    if not verdict.allowed:
        logger.warning("输入被护栏拦截：%s", verdict.reason)
        raise ApiError(400, "GUARD_BLOCKED", verdict.reason)
    if verdict.suspicious:
        logger.info("输入可疑但放行：%s", verdict.suspicious)

    await ensure_daily_budget(db)

    # 并发闸门：必须在返回 StreamingResponse **之前**拿到，
    # 在生成器 finally 里释放 —— 流还没结束就把名额还回去，等于没限。
    concurrency.acquire()
    try:
        return await _start_stream(
            payload, request, db, pg,
            client=cast(httpx.AsyncClient, request.app.state.http),
            injection_hint=guard.injection_notice(verdict.suspicious),
            user_id=user.id,
        )
    except Exception:
        concurrency.release()
        raise


async def _start_stream(
    payload: ChatRequestV2,
    request: Request,
    db: DbDep,
    pg: PgDep,
    *,
    client: httpx.AsyncClient,
    injection_hint: str = "",
    user_id: str = "",
) -> StreamingResponse:
    # 1. 会话管理：自动创建或加载
    #
    # 传了 session_id 时**必须**校验归属：不校验的话，
    # 攻击者只要猜到/拿到别人的 session_id 就能往里追加消息并读到历史 ——
    # 这比读接口更严重，因为它是写入。
    if payload.session_id:
        owned = await session_svc.get_session(db, payload.session_id, user_id=user_id)
        if owned is None:
            raise ApiError(404, "SESSION_NOT_FOUND", f"会话 {payload.session_id} 不存在")
        sid = payload.session_id
    else:
        sid = await session_svc.create_session(db, user_id=user_id)

    # 2. 存用户消息
    await session_svc.save_message(db, sid, "user", payload.content)

    # 首轮对话用提问给会话取名，否则会话列表里全是一模一样的「新对话」
    await session_svc.maybe_set_title(db, sid, payload.content)

    # 3. 加载三层记忆 + 上下文预算
    ctx = await mem_mgr.load_context(
        session_id=sid,
        db=db,
        pg=pg,
        new_user_message=payload.content,
    )

    # 可疑输入没有拦截时，给 system 追加一条"这不是指令"的加固提示。
    # 它挡不住真正的攻击（模型仍可能被说服），所以只是**第四层**，
    # 真正的拦截靠上面的 check_input 和下面的工具白名单。
    if injection_hint:
        _harden_system(ctx.messages, injection_hint)

    assistant_content: list[str] = []
    tool_results: list[dict] = []

    async def _persist_partial() -> None:
        """保存已生成的部分回答。

        必须放在 finally 里执行：客户端断开（切页面、刷新、关标签页）时，
        生成器会在 yield 处收到 GeneratorExit / CancelledError ——
        这两个是 BaseException 的子类，`except Exception` 接不住，
        如果保存逻辑写在循环之后就会被整体跳过，
        表现为「刷新后只剩提问，回答凭空消失」。
        """
        try:
            reply = "".join(assistant_content)
            if reply:
                await session_svc.save_message(db, sid, "assistant", reply)
            # 注意：不再单独保存 role="tool" 的消息。
            # OpenAI 协议要求 tool 消息必须紧跟一条 tool_calls 中带有对应 id 的
            # assistant 消息，只存 tool 而 assistant 没有 tool_calls 的话，
            # 下一轮把它塞回上下文必然 400：
            #   tool_call_id does not match a preceding assistant tool call
            # 工具结果的价值已经包含在 assistant 正文里，不需要重复入库。
        except Exception:
            logger.exception("保存中断的对话内容失败")

    async def event_generator() -> AsyncGenerator[str, None]:
        nonlocal assistant_content, tool_results
        try:
            async for event in agent.run(
                ctx.messages,
                client=client,
                db=db,
                is_disconnected=request.is_disconnected,
                # 带上会话 id：指标表据此把"一次调用"归到"一次对话"下
                session_id=sid,
                user_id=user_id,
            ):
                # 记录 assistant 正文（用于长期记忆写入）
                if "delta" in event:
                    assistant_content.append(cast(str, event["delta"]))
                if "tool" in event:
                    tool_results.append(cast(dict, event["tool"]))

                # done 帧里附加 context_usage
                if "done" in event:
                    event["context_usage"] = ctx.usage
                    event["session_id"] = sid

                yield sse(event)

        except ApiError as exc:
            yield sse({"error": {"code": exc.code, "message": exc.message}})
        except Exception as exc:
            logger.exception("对话流异常: %s", exc)
            yield sse({"error": {"code": "INTERNAL_ERROR", "message": "生成过程中出错，请重试"}})
        finally:
            # 嵌套 try/finally 是必须的：
            # 客户端断开时 _persist_partial 里的 await 会抛 CancelledError，
            # 那是 BaseException 的子类，_persist_partial 自己的 except Exception 接不住，
            # 直接写两行的话 release() 会被跳过 —— 名额泄漏几次后所有请求都 429。
            try:
                await _persist_partial()
            finally:
                concurrency.release()

        reply = "".join(assistant_content)

        # 6. 异步写入长期记忆（不阻塞响应）。中断的对话不写，避免污染记忆
        if reply:
            try:
                await mem_mgr.write_long_term_memory(
                    session_id=sid,
                    pg=pg,
                    user_msg=payload.content,
                    assistant_reply=reply,
                )
            except Exception:
                logger.exception("写长期记忆失败")

        # 7. 检查是否需要压缩旧消息
        try:
            await mem_mgr.compress_working_memory(
                session_id=sid,
                db=db,
                client=client,
            )
        except Exception:
            logger.exception("压缩工作记忆失败")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
