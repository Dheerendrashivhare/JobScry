"""Current-user settings routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.settings import SettingsRead, SettingsUpdate
from app.services.settings import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsRead)
async def get_settings(current_user: CurrentUser, session: DBSession) -> SettingsRead:
    settings = await SettingsService(session).get_or_create(current_user.id)
    return SettingsRead.model_validate(settings)


@router.patch("", response_model=SettingsRead)
async def update_settings(
    data: SettingsUpdate, current_user: CurrentUser, session: DBSession
) -> SettingsRead:
    settings = await SettingsService(session).update(current_user.id, data)
    return SettingsRead.model_validate(settings)
