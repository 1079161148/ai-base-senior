"""积木 8 · 依赖装配：端点需要的一切都从 `Depends` 进来。

【原则】依赖链单向：conn → repo → service。端点不自己 new 任何东西，
        测试里覆盖 `get_settings` 或 `get_service` 就能换环境。
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.db.session import ConnDep
from app.repositories.note_repo import NoteRepo
from app.services.note_service import NoteService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_repo(conn: ConnDep) -> NoteRepo:
    return NoteRepo(conn)


RepoDep = Annotated[NoteRepo, Depends(get_repo)]


def get_service(repo: RepoDep) -> NoteService:
    return NoteService(repo)


ServiceDep = Annotated[NoteService, Depends(get_service)]


def pagination(
    settings: SettingsDep,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    size: Annotated[int, Query(ge=1, le=1000, description="每页条数")] = 10,
) -> tuple[int, int]:
    return page, min(size, settings.page_size_max)


PaginationDep = Annotated[tuple[int, int], Depends(pagination)]


bearer_scheme = HTTPBearer(auto_error=False, description="Bearer <APP_TOKEN>")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: SettingsDep,
) -> str:
    expected = settings.token.get_secret_value()
    if credentials is None or credentials.credentials != expected:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "需要有效的 Bearer 令牌"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "writer"


Writer = Annotated[str, Depends(get_current_user)]