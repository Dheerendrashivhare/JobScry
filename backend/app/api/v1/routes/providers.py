"""Provider-catalog routes: list (any user) + admin enable/disable."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AdminUser, CurrentUser, DBSession
from app.models.enums import ProviderSlug
from app.schemas.provider import ProviderRead, ProviderUpdate
from app.services.provider import ProviderService

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderRead])
async def list_providers(_current_user: CurrentUser, session: DBSession) -> list[ProviderRead]:
    providers = await ProviderService(session).list()
    return [ProviderRead.model_validate(p) for p in providers]


@router.patch("/{slug}", response_model=ProviderRead)
async def update_provider(
    slug: ProviderSlug, data: ProviderUpdate, _admin: AdminUser, session: DBSession
) -> ProviderRead:
    provider = await ProviderService(session).set_active(slug, data.is_active)
    return ProviderRead.model_validate(provider)
