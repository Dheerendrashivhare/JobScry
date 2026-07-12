"""Deterministic weighted scoring engine (CLAUDE.md §7).

Pure domain code — no DB, no network, no LLM. The score is the *only* thing that
decides whether a job qualifies, and it is computed here and nowhere else. The LLM
never touches it (integrity rule §7): it may only explain a score that already exists.

Dimensions (per-profile weights; owner defaults in DEFAULT_SCORING_WEIGHTS):
tech-stack 40 · experience 20 · role 20 · domain/company 10 · source quality 10.
Bands: 95-100 high · 92-94 medium-high · 90-91 stretch. Gate at profile.min_score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.enums import MatchBand, ProviderSlug

# Direct-apply trust per source (§7 "source quality + direct-apply trust").
_SOURCE_TRUST: dict[ProviderSlug, int] = {
    ProviderSlug.GREENHOUSE_LEVER: 100,  # company's own ATS — most trustworthy
    ProviderSlug.APIFY_LINKEDIN: 85,
    ProviderSlug.REMOTIVE: 80,
    ProviderSlug.APIFY_NAUKRI: 75,
    ProviderSlug.SERPAPI_GOOGLE_JOBS: 70,
    ProviderSlug.ADZUNA: 70,
    ProviderSlug.JSEARCH: 65,
    ProviderSlug.JOOBLE: 65,
}

# "3-5 years", "5+ years", "minimum 4 years"
_YEARS_RANGE = re.compile(r"(\d{1,2})\s*[-–to]+\s*(\d{1,2})\s*\+?\s*(?:years|yrs|yr)", re.I)
_YEARS_MIN = re.compile(r"(\d{1,2})\s*\+\s*(?:years|yrs|yr)", re.I)
_YEARS_ANY = re.compile(r"(\d{1,2})\s*(?:years|yrs|yr)", re.I)


@dataclass
class ScoreInput:
    """Everything the engine needs, already extracted from Profile + Job."""

    profile_skills: dict[str, float]  # canonical skill name -> weight
    required_skills: set[str]
    target_roles: list[str]
    preferred_companies: list[str]
    ignored_companies: list[str]
    experience_min_years: int
    experience_max_years: int | None
    weights: dict[str, int]

    job_title: str
    job_company: str
    job_text: str  # title + description, lowercased by the engine
    job_skills: set[str]
    provider_slug: ProviderSlug
    has_direct_apply: bool = False
    has_named_recruiter: bool = False


@dataclass
class ScoreResult:
    score: int
    band: MatchBand | None  # None when below the gate
    components: dict[str, int]
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)

    @property
    def qualified(self) -> bool:
        return self.band is not None


def band_for(score: int) -> MatchBand | None:
    """Band for a score, or None when it does not clear the 90 gate (§7)."""
    if score >= 95:
        return MatchBand.HIGH
    if score >= 92:
        return MatchBand.MEDIUM_HIGH
    if score >= 90:
        return MatchBand.STRETCH
    return None


def parse_required_years(text: str) -> tuple[int | None, int | None]:
    """Best-effort (min, max) years of experience demanded by a posting."""
    match = _YEARS_RANGE.search(text)
    if match:
        low, high = int(match.group(1)), int(match.group(2))
        return (min(low, high), max(low, high))
    match = _YEARS_MIN.search(text)
    if match:
        return (int(match.group(1)), None)
    match = _YEARS_ANY.search(text)
    if match:
        return (int(match.group(1)), None)
    return (None, None)


def _score_tech_stack(data: ScoreInput, text: str) -> tuple[int, list[str], list[str]]:
    """Weighted fraction of the candidate's skills the posting actually asks for."""
    if not data.profile_skills:
        return 0, [], []

    matched: list[str] = []
    missing: list[str] = []
    matched_weight = 0.0
    total_weight = 0.0

    for skill, weight in data.profile_skills.items():
        # A required skill counts double so a missing must-have really hurts.
        effective = weight * (2.0 if skill in data.required_skills else 1.0)
        total_weight += effective
        if skill in data.job_skills or skill in text:
            matched_weight += effective
            matched.append(skill)
        else:
            missing.append(skill)

    if total_weight == 0:
        return 0, matched, missing
    return round(100 * matched_weight / total_weight), matched, missing


def _score_experience(data: ScoreInput, text: str) -> int | None:
    """None when the posting never states a requirement — see score_job()."""
    low, high = parse_required_years(text)
    if low is None:
        return None

    candidate_min = data.experience_min_years
    candidate_max = data.experience_max_years if data.experience_max_years else 60
    required_max = high if high is not None else 60

    # Overlapping bands = a genuine fit.
    if low <= candidate_max and required_max >= candidate_min:
        return 100
    # Otherwise penalise by how far outside the band the posting sits.
    gap = low - candidate_max if low > candidate_max else candidate_min - required_max
    return max(0, 100 - 20 * gap)


def _score_role(data: ScoreInput) -> int:
    title = data.job_title.lower()
    if not data.target_roles:
        return 60
    best = 0
    for role in data.target_roles:
        role_lower = role.lower().strip()
        if not role_lower:
            continue
        if role_lower == title:
            return 100
        if role_lower in title:
            best = max(best, 90)
            continue
        role_words = set(role_lower.split())
        title_words = set(title.split())
        if role_words:
            overlap = len(role_words & title_words) / len(role_words)
            best = max(best, round(100 * overlap))
    return best


def _score_domain(data: ScoreInput) -> int:
    company = data.job_company.lower().strip()
    if any(company == c.lower().strip() for c in data.ignored_companies):
        return 0
    if any(company == c.lower().strip() for c in data.preferred_companies):
        return 100
    return 60


def _score_source(data: ScoreInput) -> int:
    score = _SOURCE_TRUST.get(data.provider_slug, 60)
    if data.has_direct_apply:
        score += 10
    if data.has_named_recruiter:
        score += 5
    return min(100, score)


def score_job(data: ScoreInput, min_score: int = 90) -> ScoreResult:
    """Score a job for a profile. Never inflates — a low score stays low (§7).

    Dimensions we cannot assess are **dropped and the remaining weights renormalized**,
    rather than filled in with a guessed "neutral" number. That matters: scoring an
    unstated experience requirement as a neutral 70 used to cap an otherwise-perfect job
    at 89 — one point under the gate — so a posting that simply didn't mention years
    could never qualify however well it fit. You can't fail a requirement nobody stated.
    """
    text = f"{data.job_title} {data.job_text}".lower()

    tech, matched, missing = _score_tech_stack(data, text)
    experience = _score_experience(data, text)

    components: dict[str, int] = {
        "tech_stack": tech,
        "role": _score_role(data),
        "domain": _score_domain(data),
        "source_quality": _score_source(data),
    }
    # Absent from the breakdown = "the posting never said", not "scored zero".
    if experience is not None:
        components["experience"] = experience

    total_weight = sum(data.weights.get(k, 0) for k in components)
    if total_weight <= 0:
        return ScoreResult(0, None, components, matched, missing)

    weighted = sum(components[k] * data.weights.get(k, 0) for k in components)
    score = round(weighted / total_weight)

    band = band_for(score) if score >= min_score else None
    return ScoreResult(
        score=score,
        band=band,
        components=components,
        matched_skills=matched,
        missing_skills=missing,
    )
