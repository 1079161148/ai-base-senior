"""积木 10 · v1 汇总：新模块只在这里挂一行。"""

from fastapi import APIRouter

from app.api.v1 import notes

router = APIRouter()
router.include_router(notes.router)