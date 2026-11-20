"""依赖装配：端点需要的一切都从这里取。

【要点】测试里只要覆盖 `get_settings` 或 `get_repo`，就能换库/换令牌，
        端点代码一行不用改（第 73 章）。
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import Settings, get_settings
from db import ConnDep
from models import Priority
from repo import TodoRepo

# ============================================================
# 仓储
# ============================================================
def get_repo(conn: ConnDep) -> TodoRepo:
    return TodoRepo(conn)


RepoDep = Annotated[TodoRepo, Depends(get_repo)]


# ============================================================
# 配置
# ============================================================
SettingsDep = Annotated[Settings, Depends(get_settings)]


# ============================================================
# 分页
# ============================================================
def pagination(
    settings: SettingsDep,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    size: Annotated[int, Query(ge=1, le=1000, description="每页条数")] = 10,
) -> tuple[int, int]:
    """【要点】静态 `le=1000` 挡住离谱请求，业务上限再由配置收口（clamp）"""
    return page, min(size, settings.page_size_max)


PaginationDep = Annotated[tuple[int, int], Depends(pagination)]


def filters(
    done: Annotated[bool | None, Query(description="完成状态")] = None,
    priority: Annotated[Priority | None, Query(description="优先级")] = None,
    q: Annotated[str | None, Query(max_length=50, description="标题关键字")] = None,
) -> dict[str, object]:
    return {"done": done, "priority": priority, "q": q}


FilterDep = Annotated[dict[str, object], Depends(filters)]


# ============================================================
# 鉴权
# ============================================================
bearer_scheme = HTTPBearer(auto_error=False, description="Bearer <APP_TOKEN>")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: SettingsDep,
) -> str:
    expected = settings.token.get_secret_value()
    if credentials is None or credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "需要有效的 Bearer 令牌"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "writer"


Writer = Annotated[str, Depends(get_current_user)]