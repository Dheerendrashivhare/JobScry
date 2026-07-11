"""Provider catalog DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ProviderHealthStatus, ProviderSlug


class ProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: ProviderSlug
    display_name: str
    requires_credentials: list[str]
    is_apify: bool
    is_active: bool
    last_health_status: ProviderHealthStatus
    last_checked_at: datetime | None


class ProviderUpdate(BaseModel):
    is_active: bool
