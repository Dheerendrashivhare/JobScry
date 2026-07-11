"""Saved-search routes, nested under a profile."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DBSession, PageParams
from app.schemas.common import Page
from app.schemas.search import SearchCreate, SearchRead, SearchUpdate
from app.services.search import SearchService

router = APIRouter(prefix="/profiles/{profile_id}/searches", tags=["searches"])


@router.post("", response_model=SearchRead, status_code=status.HTTP_201_CREATED)
async def create_search(
    profile_id: int, data: SearchCreate, current_user: CurrentUser, session: DBSession
) -> SearchRead:
    return await SearchService(session).create(current_user.id, profile_id, data)


@router.get("", response_model=Page[SearchRead])
async def list_searches(
    profile_id: int, current_user: CurrentUser, session: DBSession, page: PageParams
) -> Page[SearchRead]:
    return await SearchService(session).list(current_user.id, profile_id, page)


@router.get("/{search_id}", response_model=SearchRead)
async def get_search(
    profile_id: int, search_id: int, current_user: CurrentUser, session: DBSession
) -> SearchRead:
    return await SearchService(session).get(current_user.id, profile_id, search_id)


@router.patch("/{search_id}", response_model=SearchRead)
async def update_search(
    profile_id: int,
    search_id: int,
    data: SearchUpdate,
    current_user: CurrentUser,
    session: DBSession,
) -> SearchRead:
    return await SearchService(session).update(current_user.id, profile_id, search_id, data)


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_search(
    profile_id: int, search_id: int, current_user: CurrentUser, session: DBSession
) -> None:
    await SearchService(session).delete(current_user.id, profile_id, search_id)
