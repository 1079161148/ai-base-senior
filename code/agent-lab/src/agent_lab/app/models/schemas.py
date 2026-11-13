"""S6 · 结构化输出用到的 Pydantic schema。

这些模型有三个用途，不要混：
  1. **约束模型输出**（assembled prompt + response_format）
  2. **二次校验**（模型返回什么都要过一遍 model_validate）
  3. **持久化结构**（plan 存进库时用它做序列化/反序列化）

字段尽量少而明确：每多一个可选字段，模型就多一次自由发挥的机会。
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high"]

# 与 services/tools.py 里的工具名严格一致。
# 这样计划步骤可以直接映射成一次工具调用，不需要再写一层翻译表。
ToolAction = Literal[
    "list_todos",
    "create_todo",
    "update_todo",
    "delete_todo",
    "search_docs",
    "calculator",
]


class Issue(BaseModel):
    """审阅时发现的一个问题。"""

    model_config = ConfigDict(extra="ignore")

    file: str = Field(default="", description="相关文件或模块名，可为空")
    line: int | None = Field(default=None, description="行号，未知则省略")
    severity: Severity = Field(default="medium")
    message: str = Field(min_length=1, description="问题描述，一句话说清楚")


class ReviewResult(BaseModel):
    """教材里的示例模型：审阅结论必须是程序可消费的结构。

    `issues` 用默认空列表而不是必填：审查通过时模型更愿意省略它，
    强制必填只会换来一次无意义的重试。
    """

    model_config = ConfigDict(extra="ignore")

    issues: list[Issue] = Field(default_factory=list)
    severity: Severity = "low"
    summary: str = Field(default="", description="一句话总结，不超过 40 字")


class PlanStepDraft(BaseModel):
    """模型拆解出来的一个待执行步骤。

    注意这里**没有** status / result：那些是运行时状态，
    由服务端维护。让模型输出它们只会造成"模型谎报已完成"。
    """

    model_config = ConfigDict(extra="ignore")

    action: ToolAction
    params: dict[str, object] = Field(default_factory=dict)
    description: str = Field(default="", max_length=120)
    # 是否为高危操作：由模型建议、服务端强制复核（S8 的护栏会再判一次）
    requires_human: bool = False


class PlanDraft(BaseModel):
    """任务分解的完整输出。"""

    model_config = ConfigDict(extra="ignore")

    goal: str = Field(min_length=1, max_length=200)
    steps: list[PlanStepDraft] = Field(min_length=1, max_length=8)


class JudgeScore(BaseModel):
    """S7 · LLM-as-Judge 的打分结果。

    刻意只留 1~5 的整数：让模型给 0.73 这种小数，它自己也解释不清，
    而且不同批次之间的分数会失去可比性。
    """

    model_config = ConfigDict(extra="ignore")

    score: int = Field(ge=1, le=5, description="1=完全不符合，5=完全符合")
    reason: str = Field(default="", max_length=200)
