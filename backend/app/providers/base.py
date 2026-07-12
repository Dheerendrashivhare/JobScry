"""Job-provider plugin contract and the DTOs that flow through it (CLAUDE.md §5).

A provider turns a normalized :class:`SearchQuery` into raw result dicts
(``search_jobs``), converts each to a :class:`NormalizedJob` (``normalize``), and
reports liveness (``health_check``). Adapters never touch the DB — the ingestion
service persists results. Failure policy is basic per §5 (timeout, retry-once,
mark unhealthy, continue), applied by the caller.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar

import httpx
from pydantic import BaseModel, Field

from app.models.enums import CredentialKey, ProviderHealthStatus, ProviderSlug, WorkMode


class SearchQuery(BaseModel):
    """Provider-agnostic search inputs, built from a Search recipe + profile."""

    keywords: list[str] = Field(default_factory=list)
    description_terms: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    remote: bool | None = None
    experience_min: int | None = None
    experience_max: int | None = None
    posted_after: datetime | None = None
    limit: int = 50
    # Raw provider-specific recipe (Search.params) for adapters that want it verbatim.
    params: dict[str, Any] = Field(default_factory=dict)


class NormalizedJob(BaseModel):
    """Provider output in the shape the ingestion pipeline stores as a Job."""

    provider_slug: ProviderSlug
    external_id: str | None = None
    url: str
    apply_url: str | None = None
    title: str
    company: str
    description: str | None = None
    location: str | None = None
    is_remote: bool = False
    work_mode: WorkMode | None = None
    company_headcount: int | None = None
    recruiter_name: str | None = None
    salary_raw: str | None = None
    salary_currency: str | None = None
    salary_lpa_min: Decimal | None = None
    salary_lpa_max: Decimal | None = None
    visa_sponsorship: bool | None = None
    posted_at: datetime | None = None
    valid_through: datetime | None = None
    skills: list[str] = Field(default_factory=list)
    dedup_key: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class ProviderHealth:
    status: ProviderHealthStatus
    detail: str | None = None


class JobProvider(ABC):
    slug: ClassVar[ProviderSlug]
    requires_credentials: ClassVar[list[CredentialKey]] = []

    def __init__(
        self, http: httpx.AsyncClient, credentials: dict[CredentialKey, str] | None = None
    ) -> None:
        self.http = http
        self.credentials = credentials or {}

    def _require(self, key: CredentialKey) -> str:
        value = self.credentials.get(key)
        if not value:
            raise ProviderConfigError(f"{self.slug.value} requires credential {key.value}")
        return value

    @abstractmethod
    async def search_jobs(self, query: SearchQuery) -> list[dict[str, Any]]:
        """Return raw provider result items for the query."""

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> NormalizedJob:
        """Convert one raw item into a NormalizedJob."""

    async def health_check(self) -> ProviderHealth:
        """Default: providers with no required credentials are assumed reachable."""
        missing = [k for k in self.requires_credentials if not self.credentials.get(k)]
        if missing:
            return ProviderHealth(
                ProviderHealthStatus.UNHEALTHY,
                f"missing credentials: {', '.join(k.value for k in missing)}",
            )
        return ProviderHealth(ProviderHealthStatus.UNKNOWN)


class ProviderConfigError(Exception):
    """Raised when a provider is used without its required credentials."""
