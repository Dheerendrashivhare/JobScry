"""Per-user encrypted credential routes (Apify/LLM/SerpAPI/... keys)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DBSession
from app.models.enums import CredentialKey
from app.schemas.credential import CredentialRead, CredentialSet
from app.services.credential import CredentialService

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.get("", response_model=list[CredentialRead])
async def list_credentials(current_user: CurrentUser, session: DBSession) -> list[CredentialRead]:
    return await CredentialService(session).list(current_user.id)


@router.put("", response_model=CredentialRead)
async def set_credential(
    data: CredentialSet, current_user: CurrentUser, session: DBSession
) -> CredentialRead:
    """Create or replace a stored secret. The value is encrypted; only a mask returns."""
    return await CredentialService(session).set(current_user.id, data)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_credential(
    key: CredentialKey, current_user: CurrentUser, session: DBSession
) -> None:
    await CredentialService(session).delete(current_user.id, key)
