"""Apify LinkedIn adapter — calls the Apify REST API directly (CLAUDE.md §5).

Actor ``fantastic-jobs/advanced-linkedin-job-search-api`` via
``run-sync-get-dataset-items`` (blocking run, returns items). The search recipe
(``titleSearch``/``descriptionSearch``/``locationSearch``/``aiExperienceLevelFilter``/
``removeAgency``/``populateExternalApplyURL``/``limit``) is passed through verbatim.
"""

from __future__ import annotations

from typing import Any

from app.models.enums import CredentialKey, ProviderSlug
from app.providers.adapters._common import parse_iso
from app.providers.base import JobProvider, NormalizedJob, SearchQuery
from app.providers.dedup import make_dedup_key


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class ApifyLinkedInProvider(JobProvider):
    slug = ProviderSlug.APIFY_LINKEDIN
    requires_credentials = [CredentialKey.APIFY_TOKEN]

    ACTOR = "fantastic-jobs~advanced-linkedin-job-search-api"
    RUN_TIMEOUT = 180.0

    async def search_jobs(self, query: SearchQuery) -> list[dict[str, Any]]:
        token = self._require(CredentialKey.APIFY_TOKEN)
        run_input: dict[str, Any] = dict(query.params)
        run_input.setdefault("limit", query.limit)
        if query.posted_after:
            run_input.setdefault("datePostedAfter", query.posted_after.date().isoformat())
        url = f"https://api.apify.com/v2/acts/{self.ACTOR}/run-sync-get-dataset-items"
        resp = await self.http.post(
            url, params={"token": token}, json=run_input, timeout=self.RUN_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def normalize(self, raw: dict[str, Any]) -> NormalizedJob:
        url = raw.get("url") or raw.get("linkedin_url") or ""
        external_id = str(raw["id"]) if raw.get("id") is not None else None
        locations = raw.get("locations_derived") or raw.get("locationSearch")
        location = ", ".join(locations) if isinstance(locations, list) else locations
        headcount = _as_int(raw.get("org_linkedin_headcount") or raw.get("org_linkedin_size"))
        visa = raw.get("ai_visa_sponsorship")
        return NormalizedJob(
            provider_slug=self.slug,
            external_id=external_id,
            url=url,
            apply_url=raw.get("external_apply_url") or url,
            title=raw.get("title", ""),
            company=raw.get("organization") or raw.get("company", ""),
            description=raw.get("description") or raw.get("description_text"),
            location=location,
            is_remote=bool(
                raw.get("remote_derived") or (location and "remote" in str(location).lower())
            ),
            company_headcount=headcount,
            recruiter_name=raw.get("recruiter_name"),
            visa_sponsorship=visa if isinstance(visa, bool) else None,
            posted_at=parse_iso(raw.get("date_posted")),
            valid_through=parse_iso(raw.get("date_valid_through")),
            dedup_key=make_dedup_key(url, external_id, self.slug),
            raw_payload=raw,
        )
