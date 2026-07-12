"""JSearch adapter (RapidAPI key via header)."""

from __future__ import annotations

from typing import Any

from app.models.enums import CredentialKey, ProviderSlug
from app.providers.adapters._common import parse_iso
from app.providers.base import JobProvider, NormalizedJob, SearchQuery
from app.providers.dedup import make_dedup_key
from app.providers.salary import parse_salary


class JSearchProvider(JobProvider):
    slug = ProviderSlug.JSEARCH
    requires_credentials = [CredentialKey.RAPIDAPI_KEY]

    BASE_URL = "https://jsearch.p.rapidapi.com/search"
    HOST = "jsearch.p.rapidapi.com"

    async def search_jobs(self, query: SearchQuery) -> list[dict[str, Any]]:
        key = self._require(CredentialKey.RAPIDAPI_KEY)
        terms = " ".join(query.keywords) or "developer"
        if query.locations:
            terms = f"{terms} in {query.locations[0]}"
        headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": self.HOST}
        resp = await self.http.get(
            self.BASE_URL,
            params={"query": terms, "page": "1", "num_pages": "1"},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return data[: query.limit] if isinstance(data, list) else []

    def normalize(self, raw: dict[str, Any]) -> NormalizedJob:
        url = raw.get("job_apply_link") or raw.get("job_google_link") or ""
        external_id = raw.get("job_id")
        location = ", ".join(
            p for p in (raw.get("job_city"), raw.get("job_state"), raw.get("job_country")) if p
        )
        smin, smax = raw.get("job_min_salary"), raw.get("job_max_salary")
        currency = raw.get("job_salary_currency")
        salary_raw = None
        if smin or smax:
            lo, hi = smin or smax, smax or smin
            prefix = "₹" if currency == "INR" else f"{currency or ''} "
            suffix = " per annum" if currency == "INR" else ""
            salary_raw = f"{prefix}{lo:g} - {prefix}{hi:g}{suffix}".strip()
        salary = parse_salary(salary_raw)
        return NormalizedJob(
            provider_slug=self.slug,
            external_id=external_id,
            url=url,
            apply_url=raw.get("job_apply_link"),
            title=raw.get("job_title", ""),
            company=raw.get("employer_name", ""),
            description=raw.get("job_description"),
            location=location or None,
            is_remote=bool(raw.get("job_is_remote")),
            salary_raw=salary.raw,
            salary_currency=salary.currency or currency,
            salary_lpa_min=salary.lpa_min,
            salary_lpa_max=salary.lpa_max,
            posted_at=parse_iso(raw.get("job_posted_at_datetime_utc")),
            valid_through=parse_iso(raw.get("job_offer_expiration_datetime_utc")),
            dedup_key=make_dedup_key(url, external_id, self.slug),
            raw_payload=raw,
        )
