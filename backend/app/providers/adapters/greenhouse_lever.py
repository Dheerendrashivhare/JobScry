"""Greenhouse & Lever board adapter (free).

These are per-company boards, so the search recipe supplies board tokens via
``params``: ``{"greenhouse_boards": ["acme"], "lever_boards": ["acme"]}``. Each raw
item is tagged with its source so ``normalize`` can branch. A failing board is
skipped (best-effort, §5).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.models.enums import ProviderSlug
from app.providers.adapters._common import parse_iso
from app.providers.base import JobProvider, NormalizedJob, SearchQuery
from app.providers.dedup import make_dedup_key


class GreenhouseLeverProvider(JobProvider):
    slug = ProviderSlug.GREENHOUSE_LEVER
    requires_credentials = []

    GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    LEVER_URL = "https://api.lever.co/v0/postings/{token}"

    async def search_jobs(self, query: SearchQuery) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for token in query.params.get("greenhouse_boards", []) or []:
            try:
                resp = await self.http.get(
                    self.GREENHOUSE_URL.format(token=token), params={"content": "true"}
                )
                resp.raise_for_status()
                for job in resp.json().get("jobs", []):
                    out.append({**job, "_source": "greenhouse", "_board": token})
            except httpx.HTTPError:
                continue
        for token in query.params.get("lever_boards", []) or []:
            try:
                resp = await self.http.get(
                    self.LEVER_URL.format(token=token), params={"mode": "json"}
                )
                resp.raise_for_status()
                data = resp.json()
                for job in data if isinstance(data, list) else []:
                    out.append({**job, "_source": "lever", "_board": token})
            except httpx.HTTPError:
                continue
        return out[: query.limit] if query.limit else out

    def normalize(self, raw: dict[str, Any]) -> NormalizedJob:
        if raw.get("_source") == "lever":
            return self._normalize_lever(raw)
        return self._normalize_greenhouse(raw)

    def _normalize_greenhouse(self, raw: dict[str, Any]) -> NormalizedJob:
        url = raw.get("absolute_url", "")
        external_id = str(raw["id"]) if raw.get("id") is not None else None
        location = (raw.get("location") or {}).get("name")
        return NormalizedJob(
            provider_slug=self.slug,
            external_id=external_id,
            url=url,
            apply_url=url,
            title=raw.get("title", ""),
            company=raw.get("_board", ""),
            description=raw.get("content"),
            location=location,
            is_remote=bool(location and "remote" in location.lower()),
            posted_at=parse_iso(raw.get("updated_at")),
            dedup_key=make_dedup_key(url, external_id, self.slug),
            raw_payload=raw,
        )

    def _normalize_lever(self, raw: dict[str, Any]) -> NormalizedJob:
        url = raw.get("hostedUrl", "")
        external_id = str(raw["id"]) if raw.get("id") is not None else None
        categories = raw.get("categories") or {}
        location = categories.get("location")
        posted_at = None
        if isinstance(raw.get("createdAt"), int):
            posted_at = datetime.fromtimestamp(raw["createdAt"] / 1000, tz=UTC)
        return NormalizedJob(
            provider_slug=self.slug,
            external_id=external_id,
            url=url,
            apply_url=raw.get("applyUrl") or url,
            title=raw.get("text", ""),
            company=raw.get("_board", ""),
            description=raw.get("descriptionPlain") or raw.get("description"),
            location=location,
            is_remote=bool(location and "remote" in location.lower()),
            posted_at=posted_at,
            dedup_key=make_dedup_key(url, external_id, self.slug),
            raw_payload=raw,
        )
