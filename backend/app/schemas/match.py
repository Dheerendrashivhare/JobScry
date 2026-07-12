"""Match DTOs. Scores come from the deterministic engine; LLM fields are optional."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import EligibilityStatus, MatchBand


class MatchJobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str
    location: str | None
    url: str
    apply_url: str | None
    is_remote: bool
    salary_raw: str | None
    company_headcount: int | None


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int
    score: int
    band: MatchBand
    eligibility_status: EligibilityStatus
    component_scores: dict[str, int]
    strengths: list[str]
    missing_skills: list[str]
    explanation: str | None
    recommendation: str | None
    notified: bool
    created_at: datetime
    job: MatchJobSummary


class MatchingResult(BaseModel):
    """Honest counts (§7): we never inflate to hit a target."""

    profile_id: int
    evaluated: int
    qualified: int  # scored >= the profile's gate
    below_gate: int
    excluded_by_company_size: int
    eligibility_gated: int  # qualified, but work-auth blocked (§8)
    explanations_generated: int
    llm_enabled: bool
