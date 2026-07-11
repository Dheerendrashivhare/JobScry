"""Normalized job listing and its extracted skills.

Jobs form a global catalog, deduplicated on ``dedup_key`` (listing URL/ID) per
CLAUDE.md §6 — no fuzzy cross-portal matching. Per-profile "already shown"
bookkeeping lives in :class:`~app.models.seen_job.SeenJob`; scored results live in
:class:`~app.models.match.Match`. Salary is stored raw as posted, with LPA computed
only for INR postings (CLAUDE.md §10).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, enum_column
from app.models.enums import ProviderSlug, WorkMode

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.match import Match
    from app.models.profile import Skill


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Dedup key = normalized listing URL/ID (CLAUDE.md §6). Globally unique.
    dedup_key: Mapped[str] = mapped_column(String(1024), unique=True, index=True, nullable=False)
    provider_slug: Mapped[ProviderSlug] = enum_column(ProviderSlug, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)

    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    apply_url: Mapped[str | None] = mapped_column(String(1024))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    location: Mapped[str | None] = mapped_column(String(512))
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    work_mode: Mapped[WorkMode | None] = enum_column(WorkMode, nullable=True)

    # Company-size signals for selection-odds mode (CLAUDE.md §9).
    company_headcount: Mapped[int | None] = mapped_column(Integer)
    recruiter_name: Mapped[str | None] = mapped_column(String(255))

    # Salary: raw as posted; LPA computed for INR only, no FX (CLAUDE.md §10).
    salary_raw: Mapped[str | None] = mapped_column(String(255))
    salary_currency: Mapped[str | None] = mapped_column(String(8))
    salary_lpa_min: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    salary_lpa_max: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))

    # Work-authorization signal (CLAUDE.md §8), when the provider exposes it.
    visa_sponsorship: Mapped[bool | None] = mapped_column(Boolean)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_through: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_expired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    job_skills: Mapped[list[JobSkill]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    matches: Mapped[list[Match]] = relationship(back_populates="job", cascade="all, delete-orphan")
    applications: Mapped[list[Application]] = relationship(back_populates="job")


class JobSkill(Base):
    """Association: a canonical skill mentioned by a job posting."""

    __tablename__ = "job_skills"
    __table_args__ = (UniqueConstraint("job_id", "skill_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), index=True, nullable=False
    )

    job: Mapped[Job] = relationship(back_populates="job_skills")
    skill: Mapped[Skill] = relationship(back_populates="job_skills")
