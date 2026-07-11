"""Persistent dedup store — every listing ever shown to a profile (CLAUDE.md §6).

Keyed on the listing URL/ID (``dedup_key``) so a run returns only new listings and
notifications never repeat. Kept separate from the global ``jobs`` catalog because
"seen" is per-profile state, and an entry may exist before/without a stored Job.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.profile import Profile


class SeenJob(Base):
    __tablename__ = "seen_jobs"
    __table_args__ = (UniqueConstraint("profile_id", "dedup_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    dedup_key: Mapped[str] = mapped_column(String(1024), index=True, nullable=False)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped[Profile] = relationship(back_populates="seen_jobs")
    job: Mapped[Job | None] = relationship()
