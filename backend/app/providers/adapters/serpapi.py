"""SerpAPI Google Jobs adapter (API key)."""

from __future__ import annotations

from typing import Any

from app.models.enums import CredentialKey, ProviderSlug
from app.providers.base import JobProvider, NormalizedJob, SearchQuery
from app.providers.dedup import make_dedup_key
from app.providers.salary import parse_salary


class SerpApiGoogleJobsProvider(JobProvider):
    slug = ProviderSlug.SERPAPI_GOOGLE_JOBS
    requires_credentials = [CredentialKey.SERPAPI_KEY]

    BASE_URL = "https://serpapi.com/search"

    async def search_jobs(self, query: SearchQuery) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "engine": "google_jobs",
            "api_key": self._require(CredentialKey.SERPAPI_KEY),
            "q": " ".join(query.keywords) or "developer",
        }
        if query.locations:
            params["location"] = query.locations[0]
        resp = await self.http.get(self.BASE_URL, params=params)
        resp.raise_for_status()
        results = resp.json().get("jobs_results", [])
        return results[: query.limit] if isinstance(results, list) else []

    def normalize(self, raw: dict[str, Any]) -> NormalizedJob:
        apply_options = raw.get("apply_options") or []
        apply_url = apply_options[0].get("link") if apply_options else raw.get("share_link")
        url = apply_url or raw.get("share_link") or ""
        external_id = raw.get("job_id")
        extensions = raw.get("detected_extensions") or {}
        salary = parse_salary(extensions.get("salary"))
        return NormalizedJob(
            provider_slug=self.slug,
            external_id=external_id,
            url=url,
            apply_url=apply_url,
            title=raw.get("title", ""),
            company=raw.get("company_name", ""),
            description=raw.get("description"),
            location=raw.get("location"),
            is_remote=bool(extensions.get("work_from_home")),
            salary_raw=salary.raw,
            salary_currency=salary.currency,
            salary_lpa_min=salary.lpa_min,
            salary_lpa_max=salary.lpa_max,
            dedup_key=make_dedup_key(url, external_id, self.slug),
            raw_payload=raw,
        )
