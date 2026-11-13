"""S4 · 会话与记忆模型。

会话 = 一次完整对话的容器。
消息 = 会话中的每一条 user/assistant/tool 记录。
记忆 = 摘要记忆（压缩旧消息）的持久化格式。
"""

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """前端发起新会话时传的数据。title 缺省则后端用用户第一句自动取名。"""

    title: str | None = Field(default=None, max_length=200)


class SessionInfo(BaseModel):
    """会话列表项：只展示基本信息，不包含消息。"""

    id: str
    title: str
    msg_count: int
    # 会话里最后一次提问的预览。
    # 标题只在首轮生成、之后不再变，没有这个字段的话，
    # 用户在列表里看不出某个会话后来追加了什么话题。
    last_user_message: str | None = None
    created_at: str
    updated_at: str


class SessionDetail(SessionInfo):
    """会话详情：带消息列表。"""

    messages: list[dict[str, object]]


class ChatRequestV2(BaseModel):
    """S4 版聊天请求：用 session_id 而非完整 messages。

    前端只需传 session_id + 当前问题，历史由服务端管理。
    如果没有 session_id 则自动创建新会话。
    """

    session_id: str | None = Field(default=None, max_length=50)
    content: str = Field(min_length=1, max_length=8000)


class ContextUsage(BaseModel):
    """上下文预算使用情况，done 帧里返回，前端渲染进度条。"""

    used_tokens: int
    budget_tokens: int
    ratio: float  # used / budget
    breakdown: dict[str, int]  # system / memories / working / rag