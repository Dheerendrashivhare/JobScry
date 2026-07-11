"""Candidate profile plus the skill vocabulary that matching is built on.

A profile holds all candidate-specific configuration (CLAUDE.md §4). Only *skills*
are normalized into their own tables (they form the shared vocabulary between a
candidate and a job); the remaining list-like config — target roles, preferred /
ignored companies, certifications, languages, locations, work modes, scoring
weights — lives in JSON columns on the profile per the table list in CLAUDE.md §15.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.job import JobSkill
    from app.models.match import Match
    from app.models.resume import Resume
    from app.models.search import Search
    from app.models.seen_job import SeenJob
    from app.models.user import User


# Owner's default scoring weights (CLAUDE.md §7). Stored per-profile so each
# candidate can retune without code changes.
DEFAULT_SCORING_WEIGHTS: dict[str, int] = {
    "tech_stack": 40,
    "experience": 20,
    "role": 20,
    "domain": 10,
    "source_quality": 10,
}


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    headline: Mapped[str | None] = mapped_column(String(255))
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Experience band (CLAUDE.md §7 default 2-5 yrs).
    experience_min_years: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    experience_max_years: Mapped[int | None] = mapped_column(Integer)

    # List-like candidate config (JSON, see module docstring).
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    preferred_companies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    ignored_companies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    certifications: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    languages: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    locations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    work_modes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    scoring_weights: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=lambda: dict(DEFAULT_SCORING_WEIGHTS), nullable=False
    )

    # Gate + optional selection-odds mode (CLAUDE.md §7, §9).
    min_score: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    company_size_mode: Mapped[bool] = mapped_column(default=False, nullable=False)
    max_headcount: Mapped[int | None] = mapped_column(Integer)

    user: Mapped[User] = relationship(back_populates="profiles")
    profile_skills: Mapped[list[ProfileSkill]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    resumes: Mapped[list[Resume]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    searches: Mapped[list[Search]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    matches: Mapped[list[Match]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    applications: Mapped[list[Application]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    seen_jobs: Mapped[list[SeenJob]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class Skill(Base, TimestampMixin):
    """Canonical, deduplicated skill name shared by profiles and jobs."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)

    profile_skills: Mapped[list[ProfileSkill]] = relationship(back_populates="skill")
    job_skills: Mapped[list[JobSkill]] = relationship(back_populates="skill")


class ProfileSkill(Base, TimestampMixin):
    """Association: a skill a profile has, with relative importance for scoring."""

    __tablename__ = "profile_skills"
    __table_args__ = (UniqueConstraint("profile_id", "skill_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), index=True, nullable=False
    )
    weight: Mapped[float] = mapped_column(default=1.0, nullable=False)
    is_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    proficiency: Mapped[str | None] = mapped_column(String(50))

    profile: Mapped[Profile] = relationship(back_populates="profile_skills")
    skill: Mapped[Skill] = relationship(back_populates="profile_skills")
