"""Credential repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Credential
from app.models.enums import CredentialKey


class CredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int, key: CredentialKey) -> Credential | None:
        result = await self.session.execute(
            select(Credential).where(Credential.user_id == user_id, Credential.key == key)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: int) -> Sequence[Credential]:
        result = await self.session.execute(
            select(Credential).where(Credential.user_id == user_id).order_by(Credential.key)
        )
        return result.scalars().all()

    async def delete(self, user_id: int, key: CredentialKey) -> int:
        result = await self.session.execute(
            delete(Credential).where(Credential.user_id == user_id, Credential.key == key)
        )
        return result.rowcount or 0

    def add(self, credential: Credential) -> None:
        self.session.add(credential)
