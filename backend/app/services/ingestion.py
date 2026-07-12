"""Ingestion pipeline (CLAUDE.md §14, minus scoring/notify which are later phases).

Per profile: search each enabled provider for each active saved search → normalize →
drop expired → collapse duplicates (URL/ID) → dedup against the profile's ``seen_jobs``
→ store new Jobs + skills + seen_jobs. Provider failures are isolated (retry once,
mark unhealthy, continue) so one bad provider never sinks the run (§5).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProfileNotFoundError
from app.models import Job, JobSkill, Profile, SeenJob
from app.models.enums import ProviderHealthStatus, ProviderSlug, SearchMode
from app.providers.base import JobProvider, NormalizedJob, SearchQuery
from app.providers.dedup import is_expired
from app.providers.registry import ProviderRegistry
from app.repositories.job import JobRepository
from app.repositories.profile import ProfileRepository
from app.repositories.provider import ProviderRepository
from app.repositories.search import SearchRepository
from app.repositories.seen_job import SeenJobRepository
from app.repositories.skill import SkillRepository
from app.schemas.ingestion import IngestionResult, ProviderRunSummary

_WINDOW_DAYS = {SearchMode.DAILY: 1, SearchMode.CATCHUP: 7}


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return [str(value)] if value else []


class IngestionService:
    def __init__(self, session: AsyncSession, http: httpx.AsyncClient) -> None:
        self.session = session
        self.http = http
        self.registry = ProviderRegistry(http)
        self.jobs = JobRepository(session)
        self.seen = SeenJobRepository(session)
        self.skills = SkillRepository(session)
        self.searches = SearchRepository(session)
        self.profiles = ProfileRepository(session)
        self.providers_repo = ProviderRepository(session)

    async def run_profile(self, user_id: int, profile_id: int) -> IngestionResult:
        profile = await self.profiles.get_for_user(profile_id, user_id)
        if profile is None:
            raise ProfileNotFoundError()

        enabled = await self.registry.enabled_for_user(self.session, user_id)
        by_slug = {p.slug: p for p in enabled}
        searches = [
            s
            for s in await self.searches.list_for_profile(profile_id, limit=1000, offset=0)
            if s.is_active
        ]

        collected: dict[str, NormalizedJob] = {}
        fetched: dict[ProviderSlug, int] = {}
        health: dict[ProviderSlug, tuple[bool, str | None]] = {}
        now = datetime.now(UTC)

        for search in searches:
            query = self._build_query(search, profile, now)
            if search.provider_slug is not None:
                targets = [by_slug[search.provider_slug]] if search.provider_slug in by_slug else []
            else:
                targets = enabled
            for provider in targets:
                raws, ok, error = await self._safe_search(provider, query)
                fetched[provider.slug] = fetched.get(provider.slug, 0) + len(raws)
                health[provider.slug] = (ok, error)
                for raw in raws:
                    self._collect(provider, raw, collected)
            search.last_run_at = now

        seen_keys = await self.seen.existing_keys(profile_id, list(collected))
        new_jobs = [nj for key, nj in collected.items() if key not in seen_keys]
        for nj in new_jobs:
            job = await self._store_job(nj)
            self.seen.add(
                SeenJob(
                    profile_id=profile_id, dedup_key=nj.dedup_key, job_id=job.id, first_seen_at=now
                )
            )

        await self._update_health(health, now)
        await self.session.commit()

        return IngestionResult(
            profile_id=profile_id,
            searches_run=len(searches),
            candidates=len(collected),
            new_jobs=len(new_jobs),
            providers=[
                ProviderRunSummary(
                    provider=slug,
                    fetched=fetched.get(slug, 0),
                    healthy=ok,
                    error=error,
                )
                for slug, (ok, error) in health.items()
            ],
        )

    def _build_query(self, search: Any, profile: Profile, now: datetime) -> SearchQuery:
        params = dict(search.params or {})
        keywords = (
            _as_list(params.get("keywords"))
            or _as_list(params.get("titleSearch"))
            or list(profile.target_roles)
        )
        locations = _as_list(params.get("locationSearch")) or list(profile.locations)
        window = _WINDOW_DAYS.get(search.mode, 1)
        remote = any("remote" in str(m).lower() for m in profile.work_modes) or None
        return SearchQuery(
            keywords=keywords,
            description_terms=_as_list(params.get("descriptionSearch")),
            locations=locations,
            remote=remote,
            experience_min=profile.experience_min_years,
            experience_max=profile.experience_max_years,
            posted_after=now - timedelta(days=window),
            limit=int(params.get("limit", 50)),
            params=params,
        )

    async def _safe_search(
        self, provider: JobProvider, query: SearchQuery
    ) -> tuple[list[dict[str, Any]], bool, str | None]:
        last_error: str | None = None
        for _attempt in range(2):  # try once, retry once (§5)
            try:
                return await provider.search_jobs(query), True, None
            except Exception as exc:  # isolate provider failures
                last_error = f"{type(exc).__name__}: {exc}"
        return [], False, last_error

    def _collect(
        self, provider: JobProvider, raw: dict[str, Any], collected: dict[str, NormalizedJob]
    ) -> None:
        try:
            normalized = provider.normalize(raw)
        except Exception:
            return
        if not normalized.url and not normalized.external_id:
            return
        if is_expired(normalized.valid_through):
            return
        collected.setdefault(normalized.dedup_key, normalized)

    async def _store_job(self, nj: NormalizedJob) -> Job:
        existing = await self.jobs.get_by_dedup_key(nj.dedup_key)
        if existing is not None:
            return existing
        job = Job(
            dedup_key=nj.dedup_key,
            provider_slug=nj.provider_slug,
            external_id=nj.external_id,
            url=nj.url or nj.dedup_key,
            apply_url=nj.apply_url,
            title=nj.title or "(untitled)",
            company=nj.company or "(unknown)",
            description=nj.description,
            location=nj.location,
            is_remote=nj.is_remote,
            work_mode=nj.work_mode,
            company_headcount=nj.company_headcount,
            recruiter_name=nj.recruiter_name,
            salary_raw=nj.salary_raw,
            salary_currency=nj.salary_currency,
            salary_lpa_min=nj.salary_lpa_min,
            salary_lpa_max=nj.salary_lpa_max,
            visa_sponsorship=nj.visa_sponsorship,
            posted_at=nj.posted_at,
            valid_through=nj.valid_through,
            is_expired=is_expired(nj.valid_through),
            raw_payload=nj.raw_payload,
        )
        self.jobs.add(job)
        await self.session.flush()

        seen_names: set[str] = set()
        for name in nj.skills:
            normalized_name = name.strip().lower()
            if not normalized_name or normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            skill = await self.skills.get_or_create(normalized_name)
            self.session.add(JobSkill(job_id=job.id, skill_id=skill.id))
        return job

    async def _update_health(
        self, health: dict[ProviderSlug, tuple[bool, str | None]], now: datetime
    ) -> None:
        for slug, (ok, error) in health.items():
            row = await self.providers_repo.get_by_slug(slug)
            if row is None:
                continue
            row.last_health_status = (
                ProviderHealthStatus.HEALTHY if ok else ProviderHealthStatus.UNHEALTHY
            )
            row.last_checked_at = now
            row.last_error = error[:1000] if error else None
