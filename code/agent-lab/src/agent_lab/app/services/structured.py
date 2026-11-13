"""S6 · 结构化输出：把「模型说的话」变成「程序能吃的对象」。

**核心原则：不要相信模型一定遵守 schema。**

即使开了 `response_format={"type": "json_object"}`，真实世界里依然会遇到：

    1. 输出被包在 ```json 围栏里
    2. JSON 前后带一句「好的，结果如下：」
    3. 必填字段缺失、类型写错（数字写成字符串）、枚举值越界
    4. 直接输出自然语言（部分厂商/中转站会忽略 response_format）

所以这道工序分三层，缺一层都会在生产上翻车：

    ① response_format 约束   —— 降低出错概率，但**不构成保证**
    ② 稳健的 JSON 抽取       —— 围栏、前后缀、嵌套花括号
    ③ Pydantic 二次校验      —— 唯一可信的判定
       失败 → 把**具体错误**回灌给模型重试（而不是简单重发一遍）

只做 ① 不做 ③ 的代码，看起来很好，直到模型哪天多吐一个字段。
"""

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

import httpx
from pydantic import BaseModel, ValidationError

from ..core.config import settings
from ..core.errors import ApiError
from . import llm

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# 只匹配开头的 ```json / ```JSON / ``` 三种围栏写法
_FENCE_OPEN = re.compile(r"^```[a-zA-Z]*\s*")
_FENCE_CLOSE = re.compile(r"\s*```$")


@dataclass(slots=True)
class StructuredResult(Generic[T]):
    """一次结构化调用的结果。

    attempts > 1 说明模型第一次没守规矩 —— 这个数字要进 trace，
    它是「模型对当前 schema 的听话程度」的直接度量。
    """

    value: T
    attempts: int
    raw: str


def extract_json(text: str) -> object:
    """从模型输出里抠出第一个合法 JSON 值。

    为什么不用 `json.loads(text)`：
    模型很爱在 JSON 外面裹点东西，一次 `loads` 失败就整轮报废太脆。
    这里用 raw_decode 从每个 `{` / `[` 试着解析，能读到哪算哪。
    """
    s = text.strip()
    if s.startswith("```"):
        s = _FENCE_CLOSE.sub("", _FENCE_OPEN.sub("", s)).strip()

    decoder = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch not in "{[":
            continue
        try:
            obj, _ = decoder.raw_decode(s[i:])
        except json.JSONDecodeError:
            # 这个 `{` 可能是正文里的普通字符（或片段不完整），换下一个
            continue
        return obj

    raise json.JSONDecodeError("没有找到合法的 JSON 值", s[:200], 0)


def _format_errors(exc: ValidationError) -> str:
    """把 Pydantic 的错误压成模型能看懂的短句。

    直接甩 `exc.json()` 给模型没用 —— 它看到一堆 metadata 反而更糊涂。
    只保留「哪个字段、什么错」。
    """
    lines: list[str] = []
    for err in exc.errors()[:8]:
        loc = ".".join(str(p) for p in err.get("loc", ())) or "(根)"
        lines.append(f"- 字段 {loc}：{err.get('msg', '不合法')}")
    return "\n".join(lines) if lines else str(exc)


def _repair_prompt(schema: type[BaseModel], error_text: str) -> str:
    """重试时追加的纠正消息。

    要点：**给出 schema 的精简形态**。只骂「你错了」而不给正确答案的样子，
    模型只能瞎猜；给出字段名和类型，第二次通过率会高很多。
    """
    try:
        spec = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    except Exception:  # pragma: no cover - schema 生成失败也不该炸掉主流程
        spec = "（无法生成 schema，请参考错误信息中的字段名）"
    if len(spec) > 1500:
        spec = spec[:1500] + "…（已截断）"

    return (
        "上一次输出无法通过 JSON Schema 校验：\n"
        f"{error_text}\n\n"
        "请修正后**只输出一个 JSON 对象**：不要解释、不要 markdown 围栏、不要注释。\n"
        f"必须满足的 schema：{spec}"
    )


async def _collect(
    messages: Sequence[llm.Message],
    *,
    client: httpx.AsyncClient,
    temperature: float,
) -> str:
    """把一次流式输出拼成完整文本。

    结构化场景不需要打字机效果（前端不逐字展示 JSON），
    但复用 stream_chat 能吃到同一套超时/错误映射，避免出现第二套协议实现。
    """
    parts: list[str] = []
    async for chunk in llm.stream_chat(
        messages,
        client=client,
        tools=None,
        response_format={"type": "json_object"},
        temperature=temperature,
    ):
        # reasoning 通道不收：思考过程不是结构化结果的一部分
        if chunk.delta:
            parts.append(chunk.delta)
    return "".join(parts)


async def complete_json(
    messages: Sequence[llm.Message],
    *,
    client: httpx.AsyncClient,
    schema: type[T],
    max_attempts: int | None = None,
    temperature: float | None = None,
) -> StructuredResult[T]:
    """让模型输出一个符合 `schema` 的 JSON 对象，失败自动带错误重试。

    为什么不把重试做成「原样再问一次」：
    模型第二次仍然不知道哪里错了，大概率重复同一个错误 ——
    实测带具体字段错误的重试，第二次成功率远高于盲目重发。
    """
    attempts = max_attempts or settings.STRUCTURED_MAX_ATTEMPTS
    temp = settings.STRUCTURED_TEMPERATURE if temperature is None else temperature

    # 复制一份：调用方的 messages 可能还要继续用，不能就地追加纠错消息
    convo: list[llm.Message] = [dict(m) for m in messages]
    last_error = "未知错误"

    for attempt in range(1, attempts + 1):
        text = await _collect(convo, client=client, temperature=temp)

        try:
            data = extract_json(text)
            value = schema.model_validate(data)
        except ValidationError as exc:
            last_error = _format_errors(exc)
        except json.JSONDecodeError as exc:
            last_error = f"输出不是合法 JSON（{exc.msg}）"
        else:
            if attempt > 1:
                logger.info("结构化输出第 %d 次尝试通过（schema=%s）", attempt, schema.__name__)
            return StructuredResult(value=value, attempts=attempt, raw=text)

        logger.warning(
            "结构化输出第 %d/%d 次校验失败（schema=%s）：%s",
            attempt,
            attempts,
            schema.__name__,
            last_error.replace("\n", " | ")[:200],
        )

        # 把模型刚才那次错误的输出和纠错指令一起追加，形成一次有上下文的自我修正
        convo.append({"role": "assistant", "content": text})
        convo.append({"role": "user", "content": _repair_prompt(schema, last_error)})

    raise ApiError(
        502,
        "STRUCTURED_OUTPUT_INVALID",
        f"模型连续 {attempts} 次未输出符合 {schema.__name__} 的结果：{last_error[:200]}",
    )


async def complete_object(
    prompt: str,
    *,
    client: httpx.AsyncClient,
    schema: type[T],
    system: str | None = None,
    max_attempts: int | None = None,
) -> StructuredResult[T]:
    """单轮便捷入口：给一段提示词，要一个结构化结果。"""
    messages: list[llm.Message] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return await complete_json(
        messages,
        client=client,
        schema=schema,
        max_attempts=max_attempts,
    )


def json_schema_format(schema: type[BaseModel]) -> dict[str, object]:
    """生成 `response_format` 的 json_schema 形态。

    有的厂商支持严格模式（strict），能真正约束输出；
    不支持的会忽略或报错，所以调用方必须准备好回退到 json_object。
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": cast(str, schema.__name__),
            "schema": schema.model_json_schema(),
            "strict": True,
        },
    }
