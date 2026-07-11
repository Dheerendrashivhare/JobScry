"""Saved-search / query-recipe DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProviderSlug, SearchMode


class SearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider_slug: ProviderSlug | None = None
    mode: SearchMode = SearchMode.DAILY
    is_active: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class SearchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    provider_slug: ProviderSlug | None = None
    mode: SearchMode | None = None
    is_active: bool | None = None
    params: dict[str, Any] | None = None


class SearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int
    name: str
    provider_slug: ProviderSlug | None
    mode: SearchMode
    is_active: bool
    params: dict[str, Any]
    last_run_at: datetime | None
    created_at: datetime
