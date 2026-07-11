"""Provider-catalog repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Provider
from app.models.enums import ProviderSlug


class ProviderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> Sequence[Provider]:
        result = await self.session.execute(select(Provider).order_by(Provider.id))
        return result.scalars().all()

    async def get_by_slug(self, slug: ProviderSlug) -> Provider | None:
        result = await self.session.execute(select(Provider).where(Provider.slug == slug))
        return result.scalar_one_or_none()

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Provider))
        return int(result.scalar_one())

    def add(self, provider: Provider) -> None:
        self.session.add(provider)
