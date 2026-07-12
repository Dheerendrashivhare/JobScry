"""Remotive adapter (free, no credentials) — worldwide remote jobs."""

from __future__ import annotations

from typing import Any

from app.models.enums import ProviderSlug
from app.providers.adapters._common import parse_iso
from app.providers.base import JobProvider, NormalizedJob, SearchQuery
from app.providers.dedup import make_dedup_key
from app.providers.salary import parse_salary


class RemotiveProvider(JobProvider):
    slug = ProviderSlug.REMOTIVE
    requires_credentials = []

    BASE_URL = "https://remotive.com/api/remote-jobs"

    async def search_jobs(self, query: SearchQuery) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": query.limit}
        if query.keywords:
            params["search"] = " ".join(query.keywords)
        resp = await self.http.get(self.BASE_URL, params=params)
        resp.raise_for_status()
        jobs = resp.json().get("jobs", [])
        return jobs if isinstance(jobs, list) else []

    def normalize(self, raw: dict[str, Any]) -> NormalizedJob:
        url = raw.get("url", "")
        external_id = str(raw["id"]) if raw.get("id") is not None else None
        salary = parse_salary(raw.get("salary"))
        return NormalizedJob(
            provider_slug=self.slug,
            external_id=external_id,
            url=url,
            apply_url=raw.get("url"),
            title=raw.get("title", ""),
            company=raw.get("company_name", ""),
            description=raw.get("description"),
            location=raw.get("candidate_required_location"),
            is_remote=True,
            salary_raw=salary.raw,
            salary_currency=salary.currency,
            salary_lpa_min=salary.lpa_min,
            salary_lpa_max=salary.lpa_max,
            posted_at=parse_iso(raw.get("publication_date")),
            skills=[t for t in (raw.get("tags") or []) if isinstance(t, str)],
            dedup_key=make_dedup_key(url, external_id, self.slug),
            raw_payload=raw,
        )
