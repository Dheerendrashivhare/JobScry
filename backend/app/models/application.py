"""Application tracking: a job a candidate is pursuing, and its lifecycle state."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, enum_column
from app.models.enums import ApplicationStatus, EligibilityStatus

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.profile import Profile
    from app.models.resume import Resume


class Application(Base, TimestampMixin):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("profile_id", "job_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"))

    status: Mapped[ApplicationStatus] = enum_column(
        ApplicationStatus, default=ApplicationStatus.SAVED, nullable=False
    )
    # Carried forward from matching (CLAUDE.md §8): don't let eligibility silently sink.
    eligibility_status: Mapped[EligibilityStatus | None] = enum_column(
        EligibilityStatus, nullable=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_reference: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    profile: Mapped[Profile] = relationship(back_populates="applications")
    job: Mapped[Job] = relationship(back_populates="applications")
    resume: Mapped[Resume | None] = relationship()
