"""Provider-catalog use-cases. The catalog self-seeds on first read (idempotent)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProviderNotFoundError
from app.models import Provider
from app.models.enums import ProviderSlug
from app.providers.catalog import DEFAULT_PROVIDERS
from app.repositories.provider import ProviderRepository


class ProviderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProviderRepository(session)

    async def ensure_seeded(self) -> None:
        if await self.repo.count() > 0:
            return
        for row in DEFAULT_PROVIDERS:
            self.repo.add(
                Provider(
                    slug=row["slug"],
                    display_name=row["display_name"],
                    requires_credentials=row["requires_credentials"],
                    is_apify=row["is_apify"],
                )
            )
        try:
            await self.session.commit()
        except IntegrityError:  # concurrent seed; unique(slug) already inserted them
            await self.session.rollback()

    async def list(self) -> Sequence[Provider]:
        await self.ensure_seeded()
        return await self.repo.list()

    async def set_active(self, slug: ProviderSlug, is_active: bool) -> Provider:
        await self.ensure_seeded()
        provider = await self.repo.get_by_slug(slug)
        if provider is None:
            raise ProviderNotFoundError()
        provider.is_active = is_active
        await self.session.commit()
        await self.session.refresh(provider)
        return provider
