"""Jooble adapter (API key in the URL path)."""

from __future__ import annotations

from typing import Any

from app.models.enums import CredentialKey, ProviderSlug
from app.providers.adapters._common import parse_iso
from app.providers.base import JobProvider, NormalizedJob, SearchQuery
from app.providers.dedup import make_dedup_key
from app.providers.salary import parse_salary


class JoobleProvider(JobProvider):
    slug = ProviderSlug.JOOBLE
    requires_credentials = [CredentialKey.JOOBLE_KEY]

    BASE_URL = "https://jooble.org/api/"

    async def search_jobs(self, query: SearchQuery) -> list[dict[str, Any]]:
        key = self._require(CredentialKey.JOOBLE_KEY)
        payload = {
            "keywords": " ".join(query.keywords),
            "location": query.locations[0] if query.locations else "",
        }
        resp = await self.http.post(self.BASE_URL + key, json=payload)
        resp.raise_for_status()
        jobs = resp.json().get("jobs", [])
        return jobs[: query.limit] if isinstance(jobs, list) else []

    def normalize(self, raw: dict[str, Any]) -> NormalizedJob:
        url = raw.get("link", "")
        external_id = str(raw["id"]) if raw.get("id") is not None else None
        salary = parse_salary(raw.get("salary"))
        return NormalizedJob(
            provider_slug=self.slug,
            external_id=external_id,
            url=url,
            apply_url=url,
            title=raw.get("title", ""),
            company=raw.get("company", ""),
            description=raw.get("snippet"),
            location=raw.get("location"),
            salary_raw=salary.raw,
            salary_currency=salary.currency,
            salary_lpa_min=salary.lpa_min,
            salary_lpa_max=salary.lpa_max,
            posted_at=parse_iso(raw.get("updated")),
            dedup_key=make_dedup_key(url, external_id, self.slug),
            raw_payload=raw,
        )
