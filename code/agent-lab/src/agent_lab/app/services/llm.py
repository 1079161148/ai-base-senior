"""OpenAI 兼容协议的流式对话客户端。

**为什么手写 httpx 而不用 openai SDK**：
1. SDK 会引入一份自己的协议实现，出问题时你只能猜它做了什么；
   手写能看到每一行 `data:` 长什么样 —— 这正是 S0 那节 SSE 知识的直接应用。
2. 取消、超时、错误映射这些控制点，自己拿得住。
3. 零新依赖：httpx 本来就是 fastapi 的传递依赖，已装。

**协议要点**（记住这三条就能接任何兼容厂商）：
    POST {base_url}/chat/completions
    body: {"model": "...", "messages": [...], "stream": true}
    响应: 每行 `data: {json}`，最后一行 `data: [DONE]`
"""

import json
import logging
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass, field
from typing import cast

import httpx

from ..core.config import settings
from ..core.errors import ApiError

# 消息统一用 dict 传递，不再用 ChatMessage：
# 工具调用会往对话里塞两种 Pydantic 模型表达不了的形态 ——
#   {"role": "assistant", "content": null, "tool_calls": [...]}
#   {"role": "tool", "tool_call_id": "...", "content": "..."}
# ChatMessage 的 role 只允许 system/user/assistant，也没有 tool_call_id 字段。
# 这一层只负责转发协议，不该被业务模型约束住。
Message = dict[str, object]

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMChunk:
    """一帧增量结果。

    不用 dict 是因为调用方要写 `chunk["choices"][0]["delta"]["content"]`
    这种一碰就碎的下标链；字段名固定下来，改协议时只改这里。

    delta 和 reasoning 是两个独立的通道：
      - reasoning：推理模型的"思考过程"，逐字推过来，但不是最终答案
      - delta    ：最终答案正文
    普通模型只有 delta；推理模型会先连续推好几帧 reasoning，再切到 delta。
    分开存是为了让前端把两者用不同样式展示，而不是混成一段。
    """

    delta: str = ""
    reasoning: str = ""
    # 本轮模型请求调用的工具。非空表示这一轮不是"说完就走"，
    # 而是"我要先查点东西" —— 调用方执行完工具后必须再发一轮请求。
    tool_calls: list["ToolCall"] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, int] | None = None


@dataclass(slots=True)
class ToolCall:
    """模型请求的一次工具调用。

    arguments 保留**原始 JSON 字符串**而不是解析成 dict：
    它要原样回填进下一条 assistant 消息的 tool_calls 里，上游校验的就是字符串。
    多转一道只会引入键序、空格、数字精度之类的差异。
    """

    id: str
    name: str
    arguments: str


def _upstream_error(status: int, raw: str) -> ApiError:
    """把上游的 HTTP 错误翻译成前端能看懂的语义。

    原则：**客户端没做错**，所以不返回 4xx 给他 ——
    这些错误都是我们这边的配置或上游故障，统一用 5xx（502/504）。

    同时把上游原始响应只记日志、只截前 300 字符，
    因为它常常夹着 API Key 片段、配额信息，甚至一整页 HTML。
    """
    logger.warning("模型接口返回 %s: %s", status, raw[:300])

    if status in (401, 403):
        return ApiError(
            502,
            "LLM_AUTH_ERROR",
            "模型 API Key 无效或无权限，请检查 .env 里的 LLM_API_KEY",
        )
    if status == 404:
        return ApiError(
            502,
            "LLM_MODEL_NOT_FOUND",
            f"模型 {settings.LLM_MODEL} 不存在，请检查 .env 里的 LLM_MODEL",
        )
    if status == 402:
        # 402 Payment Required：认证已经通过，是账号没有余额 / 套餐。
        # 必须和 401 分开报 —— 前者让人去充值，后者让人去换 Key。
        # 混成一个"请求失败"会让用户顺着错误方向排查很久。
        return ApiError(
            402,
            "LLM_NO_QUOTA",
            "模型账号没有可用套餐或余额不足，请到平台控制台充值后重试",
        )
    if status == 429:
        return ApiError(
            429,
            "LLM_RATE_LIMITED",
            "模型额度不足或请求过于频繁，请稍后重试",
        )
    if status >= 500:
        return ApiError(502, "LLM_UPSTREAM_ERROR", "模型服务暂时不可用，请稍后重试")
    return ApiError(502, "LLM_REQUEST_ERROR", f"模型请求失败（{status}）")


def _parse_frame(obj: dict[str, object]) -> LLMChunk:
    """从一帧 JSON 里取出增量文本。

    不同厂商的字段位置一致（OpenAI 协议），差异主要在：
      - 有些帧只带 usage，不带 choices（流结束时）
      - 有些厂商的 delta.content 是 null
    所以每一层都要用 `or` 兜底，不能直接下标。
    """
    choices = cast(list[dict[str, object]], obj.get("choices") or [])
    if not choices:
        usage = obj.get("usage")
        return LLMChunk(usage=cast(dict[str, int] | None, usage))

    choice = choices[0]
    delta = cast(dict[str, object], choice.get("delta") or {})
    content = delta.get("content")

    # 推理模型（DeepSeek-R1 系列、QwQ、o1 等）先推"思考过程"，最终答案才进 content。
    # 字段名各厂商不统一，常见的两种都认：
    #   reasoning_content —— DeepSeek 官方、硅基流动、多数中转站
    #   reasoning         —— 部分厂商
    # 普通模型这两项都是 None，reasoning 自然为空，不影响老行为。
    reasoning = delta.get("reasoning_content") or delta.get("reasoning")

    return LLMChunk(
        delta=content if isinstance(content, str) else "",
        reasoning=reasoning if isinstance(reasoning, str) else "",
        finish_reason=cast("str | None", choice.get("finish_reason")),
        usage=cast("dict[str, int] | None", obj.get("usage")),
    )


def _accumulate_tool_calls(
    buf: dict[int, dict[str, str]],
    frame: dict[str, object],
) -> None:
    """把这一帧里的 tool_calls 分片并进 buf。

    流式协议下工具调用是**挤牙膏**式到达的：

        第1帧 {"index":0,"id":"call_abc","function":{"name":"create_todo","arguments":""}}
        第2帧 {"index":0,"function":{"arguments":"{\\"ti"}}
        第3帧 {"index":0,"function":{"arguments":"tle\\":\\"买牛奶\\"}"}}

    id 和 name 只出现在开头，arguments 一截一截拼。
    靠 index 区分并行发起的多个调用（模型可能一次要求加三条待办）。
    """
    choices = cast(list[dict[str, object]], frame.get("choices") or [])
    if not choices:
        return
    delta = cast(dict[str, object], choices[0].get("delta") or {})
    raw_calls = delta.get("tool_calls")
    if not isinstance(raw_calls, list):
        return

    for raw in cast(list[object], raw_calls):
        if not isinstance(raw, dict):
            continue
        call = cast(dict[str, object], raw)

        index = call.get("index")
        idx = index if isinstance(index, int) else 0
        slot = buf.setdefault(idx, {"id": "", "name": "", "arguments": ""})

        call_id = call.get("id")
        if isinstance(call_id, str) and call_id:
            slot["id"] = call_id

        fn = call.get("function")
        if not isinstance(fn, dict):
            continue
        func = cast(dict[str, object], fn)

        name = func.get("name")
        if isinstance(name, str) and name:
            slot["name"] = name

        arguments = func.get("arguments")
        if isinstance(arguments, str):
            slot["arguments"] += arguments


def _finalize_tool_calls(buf: dict[int, dict[str, str]]) -> list[ToolCall]:
    """把累积结果转成 ToolCall，按 index 排序保证顺序稳定。"""
    calls: list[ToolCall] = []
    for idx in sorted(buf):
        slot = buf[idx]
        name = slot["name"]
        if not name:
            # 没有函数名的分片属于协议异常，丢掉比执行一个空操作安全
            continue
        calls.append(
            ToolCall(
                # 少数厂商不返回 id。补一个确定性的值，
                # 否则回填 tool 消息时 tool_call_id 对不上，上游会直接 400
                id=slot["id"] or f"call_{idx}",
                name=name,
                arguments=slot["arguments"],
            )
        )
    return calls


async def stream_chat(
    messages: Sequence[Message],
    *,
    client: httpx.AsyncClient,
    tools: Sequence[dict[str, object]] | None = None,
    response_format: dict[str, object] | None = None,
    temperature: float | None = None,
) -> AsyncGenerator[LLMChunk, None]:
    """向模型发起流式对话，逐帧产出增量。

    调用方必须把它放在 SSE 生成器里消费；本函数只负责协议，
    不关心 HTTP 状态码怎么发（那是 api 层的事）。

    response_format 用于结构化输出（S6）：
        {"type": "json_object"}                  —— 让模型只输出 JSON 对象
        {"type": "json_schema", "json_schema": {…}} —— 厂商支持严格模式时更好，
                                                     但不保证都支持，所以调用方
                                                     仍需自己做 Pydantic 二次校验。
    """
    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    payload: dict[str, object] = {
        "model": settings.LLM_MODEL,
        "messages": list(messages),
        "stream": True,
        # 流式模式默认**不返回 token 用量**，必须显式要求。
        # 打开后，最后一帧的 choices 是空数组、只带 usage ——
        # 所以解析时不能假设 choices 一定非空。
        "stream_options": {"include_usage": True},
        "max_tokens": settings.LLM_MAX_TOKENS,
        "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
    }
    if response_format:
        payload["response_format"] = response_format
    if tools:
        # tool_choice="auto"：由模型自己决定调不调。
        # 写成具体函数名会强制它每次都调，纯聊天场景就不合适了。
        payload["tools"] = list(tools)
        payload["tool_choice"] = "auto"
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    # 工具调用分片的累积区，key 是协议里的 index
    tool_buf: dict[int, dict[str, str]] = {}

    try:
        # client.stream 是异步上下文管理器：无论正常结束、抛异常还是被取消，
        # 连接都会被关闭。裸调用 client.post 会把整个响应读进内存，
        # 流式场景下那是灾难（等半天才看到第一个字）。
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                raw = (await resp.aread()).decode("utf-8", "replace")
                raise _upstream_error(resp.status_code, raw)

            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    # 空行是 SSE 的事件分隔符；其余字段（event:/id:/retry:）用不上
                    continue

                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    break

                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    # 单帧坏掉不该炸掉整条流，跳过继续读
                    logger.debug("跳过无法解析的帧: %s", data[:120])
                    continue

                frame = cast(dict[str, object], obj)
                _accumulate_tool_calls(tool_buf, frame)

                chunk = _parse_frame(frame)
                # 只过滤"纯空"的帧（只带 role 或 finish_reason 那种）。
                #
                # usage 必须单独放行：它是流的**最后一帧**，choices 是空数组，
                # 既没有 delta 也没有 reasoning。只判前两项的话，
                # 这一帧会被当成空帧丢掉 —— 表现就是"token 永远是 0"。
                if chunk.reasoning or chunk.delta or chunk.usage:
                    yield chunk

            # 流结束：这一轮如果攒到了工具调用，一次性交出去。
            # 必须等整个流读完才能交 —— arguments 拼完之前拿到的 JSON 是残缺的，
            # 提前交给执行器只会得到"解析失败"。
            if tool_buf:
                yield LLMChunk(tool_calls=_finalize_tool_calls(tool_buf))

    except httpx.TimeoutException as exc:
        # 连接超时和读取超时都会走到这里。read 超时通常是"首个 token 迟迟不来"。
        raise ApiError(504, "LLM_TIMEOUT", "模型响应超时，请稍后重试") from exc
    except httpx.HTTPError as exc:
        # DNS 失败、连接被拒、TLS 错误、连接中断等
        logger.warning("连接模型服务失败: %s", exc)
        raise ApiError(502, "LLM_UNREACHABLE", "无法连接模型服务，请检查网络或 LLM_BASE_URL") from exc
