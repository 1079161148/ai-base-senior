"""Trace 查询接口（S2，S9 起按用户隔离）。

trace 是 Agent 每一步的可回放记录，落在 `data/traces/*.json`。
这两个接口让前端（和事后复盘的你）能翻看"那次对话到底发生了什么"。

**为什么读取也走 to_thread**：
读文件是同步 IO，直接在 `async def` 里调用会阻塞事件循环。
单次只有几 KB、看起来无所谓，但这是习惯问题 ——
今天敢为 20 个小文件阻塞，明天就会为一个大文件阻塞。

**S9 的隔离做法**：trace 是文件不是表，没法在 SQL 里 WHERE。
所以列表先读完摘要再按 user_id 过滤，详情读完整个文件再校验归属。
注意"先过滤再返回"的顺序不能反：先返回再判断就等于已经泄露了。
"""

import asyncio

from fastapi import APIRouter

from ...core.errors import ApiError
from ...core.security import CurrentUserDep
from ...services import trace as trace_service

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("", summary="最近的 trace 列表")
async def list_traces(user: CurrentUserDep, limit: int = 20) -> list[dict[str, object]]:
    # 夹在 1..100：不夹的话传 limit=100000 会把整个目录读一遍
    safe_limit = max(1, min(limit, 100))

    # 多读一些再过滤：如果只读 limit 条，过滤后可能只剩 1~2 条，
    # 用户会以为"我的记录没了"。上限 100 能保证一般情况下够用。
    rows = await asyncio.to_thread(trace_service.list_recent, 100)
    mine = [r for r in rows if str(r.get("user_id") or "") == user.id]
    return mine[:safe_limit]


@router.get("/{trace_id}", summary="按 id 读取完整 trace")
async def get_trace(trace_id: str, user: CurrentUserDep) -> dict[str, object]:
    data = await asyncio.to_thread(trace_service.load, trace_id)
    if data is None:
        raise ApiError(404, "TRACE_NOT_FOUND", f"trace {trace_id} 不存在或已被清理")

    # 不属于自己的 trace 与不存在返回同样的 404
    if str(data.get("user_id") or "") != user.id:
        raise ApiError(404, "TRACE_NOT_FOUND", f"trace {trace_id} 不存在或已被清理")

    return data
