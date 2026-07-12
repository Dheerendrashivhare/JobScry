"""Adzuna adapter (app_id + app_key). Defaults to the India board (CLAUDE.md §8)."""

from __future__ import annotations

from typing import Any

from app.models.enums import CredentialKey, ProviderSlug
from app.providers.adapters._common import parse_iso
from app.providers.base import JobProvider, NormalizedJob, SearchQuery
from app.providers.dedup import make_dedup_key
from app.providers.salary import parse_salary


class AdzunaProvider(JobProvider):
    slug = ProviderSlug.ADZUNA
    requires_credentials = [CredentialKey.ADZUNA_APP_ID, CredentialKey.ADZUNA_APP_KEY]

    BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"

    async def search_jobs(self, query: SearchQuery) -> list[dict[str, Any]]:
        country = str(query.params.get("country", "in")).lower()
        params: dict[str, Any] = {
            "app_id": self._require(CredentialKey.ADZUNA_APP_ID),
            "app_key": self._require(CredentialKey.ADZUNA_APP_KEY),
            "results_per_page": query.limit,
            "content-type": "application/json",
        }
        if query.keywords:
            params["what"] = " ".join(query.keywords)
        if query.locations:
            params["where"] = query.locations[0]
        resp = await self.http.get(self.BASE_URL.format(country=country), params=params)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return [{**r, "_country": country} for r in results]

    def normalize(self, raw: dict[str, Any]) -> NormalizedJob:
        url = raw.get("redirect_url", "")
        external_id = str(raw["id"]) if raw.get("id") is not None else None
        country = raw.get("_country", "in")
        smin, smax = raw.get("salary_min"), raw.get("salary_max")
        salary_raw = None
        if smin or smax:
            lo, hi = smin or smax, smax or smin
            salary_raw = f"₹{lo:g} - ₹{hi:g} per annum" if country == "in" else f"{lo:g} - {hi:g}"
        salary = parse_salary(salary_raw)
        return NormalizedJob(
            provider_slug=self.slug,
            external_id=external_id,
            url=url,
            apply_url=url,
            title=raw.get("title", ""),
            company=(raw.get("company") or {}).get("display_name", ""),
            description=raw.get("description"),
            location=(raw.get("location") or {}).get("display_name"),
            salary_raw=salary.raw,
            salary_currency=salary.currency,
            salary_lpa_min=salary.lpa_min,
            salary_lpa_max=salary.lpa_max,
            posted_at=parse_iso(raw.get("created")),
            dedup_key=make_dedup_key(url, external_id, self.slug),
            raw_payload=raw,
        )
