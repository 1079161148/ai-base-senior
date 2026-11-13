"""对话 trace：把 Agent 每一步都记下来，能存、能看、能回放。

**为什么值得单独一个模块**：
S7 的评测、S8 的故障排查、S9 的面试复盘，全都依赖"当时到底发生了什么"。
只在日志里打一行「对话结束」，等于把过程扔了 —— 出了问题只能靠猜。

**为什么落盘成 JSON 文件而不是塞进数据库**：
trace 是"写完就不改"的日志，一次一个文件，天然可归档、可直接 git diff、
可以丢给任何工具分析。等 S7 需要按指标聚合时再迁到表里也不迟。
"""

import asyncio
import hashlib
import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# core → app → agent_lab → src → agent-lab
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
TRACE_DIR = _PROJECT_ROOT / "data" / "traces"

# trace_id 会直接拼进文件路径，必须限制字符集。
# 不校验的话，`../../.env` 这样的 id 就能读到任意文件（路径穿越）。
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# 单条记录的文本上限。思考过程可能有几千字，
# 全存进去会让 trace 文件膨胀到没法看，而前 2000 字已经足够定位问题。
_MAX_TEXT = 2000


@dataclass(slots=True)
class ToolRecord:
    """一次工具调用。"""

    name: str
    arguments: object
    result: object
    status: str
    duration_ms: float


@dataclass(slots=True)
class StepRecord:
    """一轮"模型思考 + 调用工具"。"""

    step: int
    model_output: str
    reasoning: str
    tool_calls: list[ToolRecord] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: float = 0.0


@dataclass(slots=True)
class Trace:
    """一次完整对话的可回放记录。

    S7 加的三个字段（config_fingerprint / prompt_version / tool_version）
    是"版本指纹"。没有它们，线上指标变差时只能猜是模型换了、提示词改了、
    还是工具改了 —— 有了指纹，直接按分组对比就能定位到是哪次改动。
    """

    trace_id: str
    started_at: str
    model: str
    question: str
    duration_ms: float = 0.0
    steps: list[StepRecord] = field(default_factory=list)
    usage: dict[str, object] = field(default_factory=dict)
    stopped_reason: str = "completed"
    # 会话 id：把"用户一次对话"和"一次模型调用"关联起来
    session_id: str | None = None
    # S9：归属用户。trace 里含完整问题和模型输出，
    # 不隔离等于把别人的对话内容暴露给任何人。
    user_id: str = ""
    # 配置指纹 = hash(模型 + 温度 + max_tokens + 提示词版本 + 工具版本)
    config_fingerprint: str = ""
    prompt_version: str = ""
    tool_version: str = ""
    # 是否结构化输出调用（S6），便于对比结构化/非结构化的成本与耗时
    structured: bool = False
    structured_attempts: int = 0


def new_id() -> str:
    """时间戳 + 随机后缀：按名字排序就是按时间排序，同时不会重名。"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


def sha_short(text: str, length: int = 12) -> str:
    """短哈希。用来给提示词/工具定义生成"版本号"。

    为什么不手工写 v1/v2：人会忘记改。用内容哈希，只要提示词改了一个字，
    版本号自然就变了 —— 版本号不可能和实际内容对不上。
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def fingerprint(
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    prompt_version: str,
    tool_version: str,
) -> str:
    """配置指纹：把一次对话的"全部可变量"压成一个短串。

    指标按它分组，就能回答"是哪次改动让它变慢/变贵了"。
    """
    raw = f"{model}|{temperature}|{max_tokens}|{prompt_version}|{tool_version}"
    return sha_short(raw)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clip(text: str) -> str:
    if len(text) <= _MAX_TEXT:
        return text
    return text[:_MAX_TEXT] + f"…（截断，原长 {len(text)} 字）"


async def save(trace: Trace) -> str:
    """写入磁盘，返回文件路径。

    用 to_thread 而不是直接 write_text：
    同步 IO 会阻塞事件循环，在此期间所有并发请求都卡住 ——
    这正是 S0 强调过的坑，不能在这里自己踩一遍。
    """
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    path = TRACE_DIR / f"{trace.trace_id}.json"
    payload = json.dumps(asdict(trace), ensure_ascii=False, indent=2)
    await asyncio.to_thread(path.write_text, payload, encoding="utf-8")
    return str(path)


def load(trace_id: str) -> dict[str, object] | None:
    """按 id 读取完整 trace。id 非法或文件不存在都返回 None。"""
    if not _ID_RE.match(trace_id):
        logger.warning("非法 trace_id: %r", trace_id)
        return None

    path = TRACE_DIR / f"{trace_id}.json"
    if not path.is_file():
        return None

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        logger.exception("读取 trace 失败: %s", trace_id)
        return None

    return data if isinstance(data, dict) else None


def list_recent(limit: int = 20) -> list[dict[str, object]]:
    """最近的 trace 摘要（不含 steps，避免一次返回太多数据）。"""
    if not TRACE_DIR.is_dir():
        return []

    files = sorted(
        TRACE_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]

    out: list[dict[str, object]] = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # 单个文件坏掉不该让整个列表 500 —— 跳过它继续
            continue
        if not isinstance(data, dict):
            continue
        out.append(
            {
                "trace_id": data.get("trace_id"),
                # S9：列表要能按用户过滤，所以摘要里必须带上归属
                "user_id": data.get("user_id") or "",
                "started_at": data.get("started_at"),
                "question": data.get("question"),
                "stopped_reason": data.get("stopped_reason"),
                "usage": data.get("usage"),
            }
        )
    return out
