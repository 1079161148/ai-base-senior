"""跑一条评测用例：真实调用后端，收集答案 + 工具轨迹 + 延迟 + 成本。

**为什么打 HTTP 而不是直接调 agent.run**：
    评测要测的是"用户实际体验到的东西"，包括 SSE 分帧、chat.py 的记忆装载、
    会话创建。绕过 HTTP 直接调 run()，等于测了个简化版，指标会虚高。

每条用例用**独立会话**（session_id=null 让后端自动建），
跑完删掉，避免评测把用户真实的会话列表刷满。
"""

import json
import time
from dataclasses import dataclass, field

import httpx


@dataclass(slots=True)
class CaseRunResult:
    case_id: str
    answer: str = ""
    tools: list[str] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0
    cost_cny: float = 0.0
    tokens: int = 0
    session_id: str | None = None
    stopped_reason: str = ""
    # 被护栏在入口拦截（400 GUARD_BLOCKED）。
    # 对对抗题来说这是**通过**，对标准题来说是误杀 —— 由 judge 区分。
    blocked: bool = False


async def run_case(
    client: httpx.AsyncClient,
    base_url: str,
    case_id: str,
    question: str,
    *,
    timeout: float = 120.0,
) -> CaseRunResult:
    url = f"{base_url.rstrip('/')}/api/v1/chat/stream-v2"
    result = CaseRunResult(case_id=case_id)
    started = time.perf_counter()

    try:
        async with client.stream(
            "POST",
            url,
            json={"session_id": None, "content": question},
            timeout=timeout,
        ) as resp:
            if resp.status_code != 200:
                raw = (await resp.aread()).decode("utf-8", "replace")[:300]
                # 护栏拦截是"预期的拒绝"，不是故障，必须区分开记
                if resp.status_code == 400 and "GUARD_BLOCKED" in raw:
                    result.blocked = True
                    result.answer = "[已被护栏拦截]"
                    return result
                result.error = f"HTTP {resp.status_code}: {raw}"
                return result

            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = json.loads(line[len("data:"):].strip() or "{}")
                if not isinstance(payload, dict):
                    continue

                if "error" in payload:
                    err = payload["error"]
                    result.error = str(err.get("message") if isinstance(err, dict) else err)
                    break

                if payload.get("delta"):
                    result.answer += str(payload["delta"])

                tool = payload.get("tool")
                if isinstance(tool, dict) and tool.get("status") == "running":
                    name = str(tool.get("name") or "")
                    if name and name not in result.tools:
                        result.tools.append(name)

                if payload.get("done"):
                    usage = payload.get("usage") or {}
                    if isinstance(usage, dict):
                        result.cost_cny = float(usage.get("cost_cny") or 0.0)
                        result.tokens = int(usage.get("total_tokens") or 0)
                        result.stopped_reason = str(usage.get("stopped_reason") or "")
                    if payload.get("session_id"):
                        result.session_id = str(payload["session_id"])
                    break
    except httpx.TimeoutException:
        result.error = f"超时（>{timeout:.0f}s）"
    except Exception as exc:  # 评测脚本不能因为一条用例崩掉整批
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        result.duration_ms = round((time.perf_counter() - started) * 1000, 1)

    return result


async def cleanup_session(client: httpx.AsyncClient, base_url: str, session_id: str | None) -> None:
    """删掉评测产生的会话。失败不报错 —— 遗留一条会话比中断整批评测轻。"""
    if not session_id:
        return
    try:
        await client.delete(f"{base_url.rstrip('/')}/api/v1/sessions/{session_id}", timeout=10)
    except Exception:
        pass
