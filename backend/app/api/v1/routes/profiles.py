"""Profile routes (scoped to the current user) + per-profile skills."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DBSession, PageParams
from app.schemas.common import Page
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileSkillCreate, ProfileUpdate
from app.services.profile import ProfileService

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
    data: ProfileCreate, current_user: CurrentUser, session: DBSession
) -> ProfileRead:
    return await ProfileService(session).create(current_user.id, data)


@router.get("", response_model=Page[ProfileRead])
async def list_profiles(
    current_user: CurrentUser, session: DBSession, page: PageParams
) -> Page[ProfileRead]:
    return await ProfileService(session).list(current_user.id, page)


@router.get("/{profile_id}", response_model=ProfileRead)
async def get_profile(
    profile_id: int, current_user: CurrentUser, session: DBSession
) -> ProfileRead:
    return await ProfileService(session).get(current_user.id, profile_id)


@router.patch("/{profile_id}", response_model=ProfileRead)
async def update_profile(
    profile_id: int, data: ProfileUpdate, current_user: CurrentUser, session: DBSession
) -> ProfileRead:
    return await ProfileService(session).update(current_user.id, profile_id, data)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_profile(profile_id: int, current_user: CurrentUser, session: DBSession) -> None:
    await ProfileService(session).delete(current_user.id, profile_id)


@router.post(
    "/{profile_id}/skills", response_model=ProfileRead, status_code=status.HTTP_201_CREATED
)
async def add_profile_skill(
    profile_id: int, data: ProfileSkillCreate, current_user: CurrentUser, session: DBSession
) -> ProfileRead:
    return await ProfileService(session).add_skill(current_user.id, profile_id, data)


@router.delete(
    "/{profile_id}/skills/{profile_skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def remove_profile_skill(
    profile_id: int, profile_skill_id: int, current_user: CurrentUser, session: DBSession
) -> None:
    await ProfileService(session).remove_skill(current_user.id, profile_id, profile_skill_id)
