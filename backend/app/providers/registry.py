"""Provider registry — maps slugs to adapters and enables them per user.

A provider is enabled for a user only when it is active in the catalog and all of
its required credentials are present in that user's encrypted store (CLAUDE.md §5).
"""

from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProviderSlug
from app.providers.adapters import (
    AdzunaProvider,
    ApifyLinkedInProvider,
    ApifyNaukriProvider,
    GreenhouseLeverProvider,
    JoobleProvider,
    JSearchProvider,
    RemotiveProvider,
    SerpApiGoogleJobsProvider,
)
from app.providers.base import JobProvider
from app.services.credential import CredentialService
from app.services.provider import ProviderService

PROVIDER_CLASSES: dict[ProviderSlug, type[JobProvider]] = {
    ProviderSlug.REMOTIVE: RemotiveProvider,
    ProviderSlug.GREENHOUSE_LEVER: GreenhouseLeverProvider,
    ProviderSlug.ADZUNA: AdzunaProvider,
    ProviderSlug.JOOBLE: JoobleProvider,
    ProviderSlug.JSEARCH: JSearchProvider,
    ProviderSlug.SERPAPI_GOOGLE_JOBS: SerpApiGoogleJobsProvider,
    ProviderSlug.APIFY_LINKEDIN: ApifyLinkedInProvider,
    ProviderSlug.APIFY_NAUKRI: ApifyNaukriProvider,
}


class ProviderRegistry:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def enabled_for_user(self, session: AsyncSession, user_id: int) -> list[JobProvider]:
        catalog = await ProviderService(session).list()  # self-seeds if empty
        secrets = await CredentialService(session).get_all_secrets(user_id)
        enabled: list[JobProvider] = []
        for row in catalog:
            if not row.is_active:
                continue
            provider_cls = PROVIDER_CLASSES.get(row.slug)
            if provider_cls is None:
                continue
            if all(key in secrets for key in provider_cls.requires_credentials):
                credentials = {key: secrets[key] for key in provider_cls.requires_credentials}
                enabled.append(provider_cls(self.http, credentials))
        return enabled
