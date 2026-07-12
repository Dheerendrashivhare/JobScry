"""Apify Naukri adapter — Apify REST, actor muhammetakkurtt/naukri-job-scraper."""

from __future__ import annotations

from typing import Any

from app.models.enums import CredentialKey, ProviderSlug
from app.providers.adapters._common import parse_iso
from app.providers.base import JobProvider, NormalizedJob, SearchQuery
from app.providers.dedup import make_dedup_key
from app.providers.salary import parse_salary


class ApifyNaukriProvider(JobProvider):
    slug = ProviderSlug.APIFY_NAUKRI
    requires_credentials = [CredentialKey.APIFY_TOKEN]

    ACTOR = "muhammetakkurtt~naukri-job-scraper"
    RUN_TIMEOUT = 180.0

    async def search_jobs(self, query: SearchQuery) -> list[dict[str, Any]]:
        token = self._require(CredentialKey.APIFY_TOKEN)
        run_input: dict[str, Any] = dict(query.params)
        if query.keywords:
            run_input.setdefault("keyword", " ".join(query.keywords))
        run_input.setdefault("sortBy", "date")
        run_input.setdefault("maxJobs", max(query.limit, 50))  # actor minimum is 50
        url = f"https://api.apify.com/v2/acts/{self.ACTOR}/run-sync-get-dataset-items"
        resp = await self.http.post(
            url, params={"token": token}, json=run_input, timeout=self.RUN_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def normalize(self, raw: dict[str, Any]) -> NormalizedJob:
        url = raw.get("jobUrl") or raw.get("url") or ""
        external_id = str(raw["jobId"]) if raw.get("jobId") is not None else None
        salary = parse_salary(raw.get("salary"))
        return NormalizedJob(
            provider_slug=self.slug,
            external_id=external_id,
            url=url,
            apply_url=url,
            title=raw.get("title", ""),
            company=raw.get("companyName") or raw.get("company", ""),
            description=raw.get("jobDescription") or raw.get("description"),
            location=raw.get("location"),
            salary_raw=salary.raw,
            salary_currency=salary.currency,
            salary_lpa_min=salary.lpa_min,
            salary_lpa_max=salary.lpa_max,
            posted_at=parse_iso(raw.get("postedDate")),
            dedup_key=make_dedup_key(url, external_id, self.slug),
            raw_payload=raw,
        )
