"""对话数据契约。

**为什么 role 用 Literal 而不是 str**：
OpenAI 兼容协议只认这三种角色，写成 str 的话传个 "bot" 也会通过校验，
到上游才报 400，错误离现场太远。类型本身就该是第一道校验。
"""

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: Role
    # 单条上限 8000 字符：不设的话，一个超长 prompt 可能直接把上下文撑爆，
    # 上游返回 400 context_length_exceeded，用户看到的却是"生成失败"。
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    # 上限 50 条：多轮对话迟早要裁剪历史，
    # 在入口处拦一道比事后靠上游报错更可控。
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)


class ChatStreamEvent(BaseModel):
    """SSE 单帧结构。

    **这个模型不参与响应序列化**（接口返回的是 text/event-stream），
    它存在的意义是让 OpenAPI 文档能描述"这一帧长什么样"。
    没有它，文档里这个接口的响应体是一片空白。
    """

    delta: str | None = Field(default=None, description="本次增量文本")
    done: bool | None = Field(default=None, description="是否结束")
    usage: dict[str, int] | None = Field(default=None, description="字符数 / 分片数统计")
    error: dict[str, str] | None = Field(default=None, description="流内错误（code + message）")
