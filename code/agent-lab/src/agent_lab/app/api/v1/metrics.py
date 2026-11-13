"""S7 · 指标接口：给看板、给 CI 门禁、给 Prometheus。

三个消费方，一个数据源：
    前端看板   → /metrics/summary
    人看失败详情 → /metrics/failures
    监控系统    → /metrics/prometheus（文本格式，不用额外依赖）
"""

import aiosqlite
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from typing import Annotated

from ...core.db import get_db
from ...core.security import CurrentUserDep
from ...services import metrics as metrics_svc

router = APIRouter(prefix="/metrics", tags=["metrics"])

DbDep = Annotated[aiosqlite.Connection, Depends(get_db)]


@router.get("/summary")
async def summary(user: CurrentUserDep, db: DbDep, days: int = 7) -> dict[str, object]:
    """看板主接口：成功率 / P50·P95·P99 / 成本 / 按天 / 按配置指纹。

    只统计当前用户自己的请求 —— 指标里带 question 原文，
    不隔离等于把别人的提问曝光在看板上。
    """
    return await metrics_svc.summary(db, days=max(1, min(days, 90)), user_id=user.id)


@router.get("/failures")
async def failures(
    user: CurrentUserDep,
    db: DbDep,
    limit: int = 20,
) -> list[dict[str, object]]:
    return await metrics_svc.recent_failures(
        db, limit=min(limit, 100), user_id=user.id
    )


@router.get("/prometheus", response_class=PlainTextResponse)
async def prometheus(db: DbDep, days: int = 1) -> str:
    """Prometheus 文本暴露格式。

    不引 prometheus-client 的原因：我们只需要四个数字，
    手写这几行比多一个依赖更划算（也更容易看懂）。

    **这个接口故意不鉴权、也不按用户过滤**：
    抓取端（Prometheus）不会带 token，而这里只有全局聚合数字，
    没有任何问题原文或回答内容 —— 泄露的只是"总量"。
    如果要按租户暴露，正确做法是加 label，而不是在这里做隔离。
    """
    data = await metrics_svc.summary(db, days=max(1, min(days, 30)), user_id=None)
    lines = [
        "# HELP agent_requests_total 窗口内对话请求数",
        "# TYPE agent_requests_total gauge",
        f"agent_requests_total {data['requests']}",
        "# HELP agent_success_rate 成功率",
        "# TYPE agent_success_rate gauge",
        f"agent_success_rate {data['success_rate']}",
        "# HELP agent_latency_p95_ms P95 延迟（毫秒）",
        "# TYPE agent_latency_p95_ms gauge",
        f"agent_latency_p95_ms {data['p95_ms']}",
        "# HELP agent_cost_cny_total 窗口内总成本（元）",
        "# TYPE agent_cost_cny_total gauge",
        f"agent_cost_cny_total {data['total_cost_cny']}",
    ]
    return "\n".join(lines) + "\n"
