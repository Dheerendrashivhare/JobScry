"""Default job-provider catalog (CLAUDE.md §5).

Seed metadata only — the actual search/normalize adapters land in Phase 5. Each
row lists the ``CredentialKey`` values a user must supply before the provider can
run for them; providers with an empty list (Remotive, Greenhouse/Lever) are always
usable. Wellfound is intentionally absent (dropped, §5).
"""

from __future__ import annotations

from typing import TypedDict

from app.models.enums import CredentialKey, ProviderSlug


class ProviderSeed(TypedDict):
    slug: ProviderSlug
    display_name: str
    requires_credentials: list[str]
    is_apify: bool


DEFAULT_PROVIDERS: list[ProviderSeed] = [
    {
        "slug": ProviderSlug.ADZUNA,
        "display_name": "Adzuna",
        "requires_credentials": [
            CredentialKey.ADZUNA_APP_ID.value,
            CredentialKey.ADZUNA_APP_KEY.value,
        ],
        "is_apify": False,
    },
    {
        "slug": ProviderSlug.JOOBLE,
        "display_name": "Jooble",
        "requires_credentials": [CredentialKey.JOOBLE_KEY.value],
        "is_apify": False,
    },
    {
        "slug": ProviderSlug.JSEARCH,
        "display_name": "JSearch (RapidAPI)",
        "requires_credentials": [CredentialKey.RAPIDAPI_KEY.value],
        "is_apify": False,
    },
    {
        "slug": ProviderSlug.REMOTIVE,
        "display_name": "Remotive",
        "requires_credentials": [],
        "is_apify": False,
    },
    {
        "slug": ProviderSlug.GREENHOUSE_LEVER,
        "display_name": "Greenhouse & Lever boards",
        "requires_credentials": [],
        "is_apify": False,
    },
    {
        "slug": ProviderSlug.SERPAPI_GOOGLE_JOBS,
        "display_name": "Google Jobs (SerpAPI)",
        "requires_credentials": [CredentialKey.SERPAPI_KEY.value],
        "is_apify": False,
    },
    {
        "slug": ProviderSlug.APIFY_LINKEDIN,
        "display_name": "LinkedIn (Apify)",
        "requires_credentials": [CredentialKey.APIFY_TOKEN.value],
        "is_apify": True,
    },
    {
        "slug": ProviderSlug.APIFY_NAUKRI,
        "display_name": "Naukri (Apify)",
        "requires_credentials": [CredentialKey.APIFY_TOKEN.value],
        "is_apify": True,
    },
]
