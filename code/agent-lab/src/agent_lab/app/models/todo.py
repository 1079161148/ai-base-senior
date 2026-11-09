"""待办的数据契约。

**为什么拆成三个模型而不是一个**：

| 模型 | 方向 | 作用 |
|------|------|------|
| `TodoCreate` | 进 | 只允许客户端设置 title —— id / created_at 由服务端决定 |
| `TodoUpdate` | 进 | 字段全部可选，支持局部更新（PATCH 语义） |
| `TodoOut` | 出 | 决定前端能看见哪些字段 |

如果一个 Todo 模型到处传，客户端就能在 POST body 里塞 `"id": 999`，
这就从"代码不优雅"变成了"越权写入"。
"""

from pydantic import BaseModel, Field

from ..core.time import UtcDatetime


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="待办内容")


class TodoUpdate(BaseModel):
    """局部更新：只传要改的字段。全为 None 等价于不对数据库做任何修改。"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    done: bool | None = None


class TodoOut(BaseModel):
    id: int
    title: str
    done: bool
    # 用 UtcDatetime 而不是 str：字段是 datetime，格式由 core/time.py 统一决定。
    # 以后加 updated_at 只需写 `updated_at: UtcDatetime`，不必再写任何格式化代码。
    created_at: UtcDatetime
