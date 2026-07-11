"""Job-provider catalog.

A global registry row per provider (CLAUDE.md §5). Whether a provider is *usable*
for a given user is derived at runtime from that user's encrypted credentials
(``requires_credentials``); a provider with no requirements (e.g. Remotive) is
always usable. Health is best-effort per §5 (timeout, retry-once, mark unhealthy).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, enum_column
from app.models.enums import ProviderHealthStatus, ProviderSlug


class Provider(Base, TimestampMixin):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[ProviderSlug] = enum_column(ProviderSlug, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # CredentialKey values this provider needs before it can run for a user.
    requires_credentials: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_apify: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_health_status: Mapped[ProviderHealthStatus] = enum_column(
        ProviderHealthStatus, default=ProviderHealthStatus.UNKNOWN, nullable=False
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(1024))
