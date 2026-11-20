"""第 65 章 · admin 模块。

【要点】`dependencies=[Depends(require_admin)]` 挂一次，
        该 router 下**所有**端点都受保护，包括后来新增的。
"""

from fastapi import APIRouter, Depends

import store
from dependencies import require_admin
from models import AdminStats

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/stats", summary="后台统计")
def admin_stats() -> AdminStats:
    return AdminStats(users=len(store.USERS), items=len(store.ITEMS))


# 【要点】内部端点不进文档，但**仍然**受 router 级依赖保护
@router.get("/debug", include_in_schema=False)
def admin_debug() -> dict[str, int]:
    return {"users": len(store.USERS), "items": len(store.ITEMS)}


# 【要点】`deprecated=True` 让文档标记废弃，但端点仍可调用
@router.get("/legacy", deprecated=True, summary="旧接口")
def admin_legacy() -> dict[str, str]:
    return {"status": "deprecated"}