"""健康检查。

存在的意义不是"给运维看"，而是：
1. 让前端有一个绝对不会失败的接口可以联调
2. 让部署平台有探针地址
"""

from fastapi import APIRouter
from pydantic import BaseModel

# 包内相对导入：`.` = 当前包 v1，`..` = api，`...` = app
# 等价于 from agent_lab.app.core.config import settings
from ...core.config import settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="健康检查")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.VERSION)
