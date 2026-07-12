"""Ingestion-run result DTOs."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import ProviderSlug


class ProviderRunSummary(BaseModel):
    provider: ProviderSlug
    fetched: int
    healthy: bool
    error: str | None = None


class IngestionResult(BaseModel):
    profile_id: int
    searches_run: int
    candidates: int  # unique normalized listings before per-profile dedup
    new_jobs: int
    providers: list[ProviderRunSummary]
