"""Profile + profile-skill DTOs.

A profile carries all candidate config (CLAUDE.md §4). List-like fields are free-form
strings so nothing is profession-hardcoded; ``scoring_weights`` defaults to the owner's
weights (§7) when omitted.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProfileSkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    weight: float = Field(default=1.0, ge=0)
    is_required: bool = False
    proficiency: str | None = Field(default=None, max_length=50)


class ProfileSkillRead(BaseModel):
    id: int
    name: str
    weight: float
    is_required: bool
    proficiency: str | None


class ProfileBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    headline: str | None = Field(default=None, max_length=255)
    experience_min_years: int = Field(default=0, ge=0, le=60)
    experience_max_years: int | None = Field(default=None, ge=0, le=60)
    target_roles: list[str] = Field(default_factory=list)
    preferred_companies: list[str] = Field(default_factory=list)
    ignored_companies: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    work_modes: list[str] = Field(default_factory=list)
    min_score: int = Field(default=90, ge=0, le=100)
    company_size_mode: bool = False
    max_headcount: int | None = Field(default=None, ge=1)


class ProfileCreate(ProfileBase):
    is_default: bool = False
    scoring_weights: dict[str, int] | None = None
    skills: list[ProfileSkillCreate] = Field(default_factory=list)


class ProfileUpdate(BaseModel):
    """Partial update — only provided fields change."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    headline: str | None = Field(default=None, max_length=255)
    experience_min_years: int | None = Field(default=None, ge=0, le=60)
    experience_max_years: int | None = Field(default=None, ge=0, le=60)
    target_roles: list[str] | None = None
    preferred_companies: list[str] | None = None
    ignored_companies: list[str] | None = None
    certifications: list[str] | None = None
    languages: list[str] | None = None
    locations: list[str] | None = None
    work_modes: list[str] | None = None
    scoring_weights: dict[str, int] | None = None
    min_score: int | None = Field(default=None, ge=0, le=100)
    company_size_mode: bool | None = None
    max_headcount: int | None = Field(default=None, ge=1)
    is_default: bool | None = None


class ProfileRead(ProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_default: bool
    scoring_weights: dict[str, int]
    skills: list[ProfileSkillRead]
    created_at: datetime
