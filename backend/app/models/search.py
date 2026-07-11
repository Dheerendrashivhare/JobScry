"""Saved search template / query recipe (CLAUDE.md §4, §5).

Provider-specific parameters (the LinkedIn ``titleSearch`` / ``descriptionSearch``
recipe, Naukri ``keyword`` / ``freshness``, etc.) are stored as an opaque JSON
``params`` blob so each provider adapter reads what it needs without schema churn.
Ships seeded with the owner's proven LinkedIn default in a later phase.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, enum_column
from app.models.enums import ProviderSlug, SearchMode

if TYPE_CHECKING:
    from app.models.profile import Profile


class Search(Base, TimestampMixin):
    __tablename__ = "searches"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Null = applies to every enabled provider; otherwise targets one provider.
    provider_slug: Mapped[ProviderSlug | None] = enum_column(ProviderSlug, nullable=True)
    mode: Mapped[SearchMode] = enum_column(SearchMode, default=SearchMode.DAILY, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped[Profile] = relationship(back_populates="searches")
