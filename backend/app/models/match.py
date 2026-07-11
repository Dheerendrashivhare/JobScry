"""Scored match between a profile and a job.

The numeric score and component breakdown are produced by the deterministic
rule-based engine (CLAUDE.md §7); ``explanation`` / ``strengths`` /
``recommendation`` / ``tailored_resume`` are optionally enriched by the LLM and are
never allowed to change the score (integrity rule §7).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, enum_column
from app.models.enums import EligibilityStatus, MatchBand

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.profile import Profile
    from app.models.resume import Resume


class Match(Base, TimestampMixin):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("profile_id", "job_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )

    score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    band: Mapped[MatchBand] = enum_column(MatchBand, nullable=False)
    eligibility_status: Mapped[EligibilityStatus] = enum_column(
        EligibilityStatus, default=EligibilityStatus.ACTIONABLE, nullable=False
    )
    # Per-dimension score breakdown (tech_stack/experience/role/domain/source).
    component_scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # LLM-enriched, optional (require user's LLM key).
    explanation: Mapped[str | None] = mapped_column(Text)
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    missing_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text)

    tailored_resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL")
    )
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    profile: Mapped[Profile] = relationship(back_populates="matches")
    job: Mapped[Job] = relationship(back_populates="matches")
    tailored_resume: Mapped[Resume | None] = relationship(
        back_populates="tailored_matches", foreign_keys=[tailored_resume_id]
    )
