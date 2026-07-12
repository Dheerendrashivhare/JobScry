"""Unit tests for the deterministic scoring engine and work-auth gate (§7, §8)."""

from __future__ import annotations

from app.matching.eligibility import assess_eligibility
from app.matching.scoring import ScoreInput, band_for, parse_required_years, score_job
from app.models.enums import EligibilityStatus, MatchBand, ProviderSlug

WEIGHTS = {"tech_stack": 40, "experience": 20, "role": 20, "domain": 10, "source_quality": 10}


def _input(**overrides: object) -> ScoreInput:
    base = dict(
        profile_skills={"python": 1.0, "fastapi": 1.0, "postgresql": 1.0},
        required_skills={"python", "fastapi"},
        target_roles=["Backend Engineer", "Python Developer"],
        preferred_companies=[],
        ignored_companies=[],
        experience_min_years=2,
        experience_max_years=5,
        weights=dict(WEIGHTS),
        job_title="Backend Engineer",
        job_company="Acme",
        job_text="We need Python, FastAPI and PostgreSQL. 3-5 years experience.",
        job_skills={"python", "fastapi", "postgresql"},
        provider_slug=ProviderSlug.GREENHOUSE_LEVER,
        has_direct_apply=True,
        has_named_recruiter=False,
    )
    base.update(overrides)
    return ScoreInput(**base)  # type: ignore[arg-type]


# --- bands ------------------------------------------------------------------


def test_bands() -> None:
    assert band_for(97) is MatchBand.HIGH
    assert band_for(93) is MatchBand.MEDIUM_HIGH
    assert band_for(90) is MatchBand.STRETCH
    assert band_for(89) is None  # below the gate


def test_parse_required_years() -> None:
    assert parse_required_years("3-5 years experience") == (3, 5)
    assert parse_required_years("5+ years") == (5, None)
    assert parse_required_years("minimum 4 yrs") == (4, None)
    assert parse_required_years("no numbers here") == (None, None)


# --- scoring ----------------------------------------------------------------


def test_perfect_fit_qualifies_high() -> None:
    result = score_job(_input())
    assert result.components["tech_stack"] == 100
    assert result.components["experience"] == 100
    assert result.components["role"] == 100
    assert result.score >= 95
    assert result.band is MatchBand.HIGH
    assert result.qualified is True
    assert set(result.matched_skills) == {"python", "fastapi", "postgresql"}
    assert result.missing_skills == []


def test_missing_required_skill_tanks_the_score() -> None:
    # Job wants none of the candidate's stack.
    result = score_job(
        _input(
            job_text="We need Java, Spring and Kafka. 3-5 years experience.",
            job_skills={"java", "spring"},
        )
    )
    assert result.components["tech_stack"] == 0
    assert result.score < 90
    assert result.band is None
    assert result.qualified is False  # never inflated to reach the gate
    assert set(result.missing_skills) == {"python", "fastapi", "postgresql"}


def test_experience_mismatch_penalised() -> None:
    result = score_job(_input(job_text="Python FastAPI PostgreSQL. 12+ years experience."))
    # Candidate tops out at 5; posting wants 12+ -> 7 years past the band.
    assert result.components["experience"] < 100
    assert result.score < 95


def test_unstated_experience_is_neutral_not_free() -> None:
    result = score_job(_input(job_text="Python FastAPI PostgreSQL. Great team."))
    assert result.components["experience"] == 70


def test_ignored_company_zeroes_domain() -> None:
    result = score_job(_input(ignored_companies=["Acme"]))
    assert result.components["domain"] == 0
    assert result.score < score_job(_input()).score


def test_preferred_company_boosts_domain() -> None:
    result = score_job(_input(preferred_companies=["Acme"]))
    assert result.components["domain"] == 100


def test_role_mismatch_lowers_score() -> None:
    result = score_job(_input(job_title="Data Scientist"))
    assert result.components["role"] < 60
    assert result.score < 95


def test_source_quality_reflects_provider_trust() -> None:
    ats = score_job(_input(provider_slug=ProviderSlug.GREENHOUSE_LEVER))
    aggregator = score_job(_input(provider_slug=ProviderSlug.JOOBLE, has_direct_apply=False))
    assert ats.components["source_quality"] > aggregator.components["source_quality"]


def test_profile_with_no_skills_cannot_qualify() -> None:
    result = score_job(_input(profile_skills={}, required_skills=set()))
    assert result.components["tech_stack"] == 0
    assert result.qualified is False


def test_custom_weights_change_the_outcome() -> None:
    # A profile that only cares about role should score well despite a stack miss.
    weights = {"tech_stack": 0, "experience": 0, "role": 100, "domain": 0, "source_quality": 0}
    result = score_job(_input(weights=weights, job_skills=set(), job_text="Java only"))
    assert result.components["role"] == 100
    assert result.score == 100


# --- eligibility (§8) -------------------------------------------------------


def test_india_role_is_actionable() -> None:
    result = assess_eligibility("Bengaluru, India", is_remote=False)
    assert result.status is EligibilityStatus.ACTIONABLE
    assert result.actionable


def test_offshore_without_sponsorship_is_gated() -> None:
    result = assess_eligibility("Berlin, Germany", is_remote=False, description="Great team.")
    assert result.status is EligibilityStatus.ELIGIBILITY_GATED


def test_offshore_with_explicit_sponsorship_is_actionable() -> None:
    result = assess_eligibility(
        "Berlin, Germany", is_remote=False, description="Visa sponsorship available."
    )
    assert result.status is EligibilityStatus.ACTIONABLE


def test_global_remote_is_actionable_unless_blocked() -> None:
    open_remote = assess_eligibility("Remote - Worldwide", is_remote=True, description="")
    assert open_remote.status is EligibilityStatus.ACTIONABLE

    blocked = assess_eligibility(
        "Remote - US",
        is_remote=True,
        description="You must be authorized to work in the United States.",
    )
    assert blocked.status is EligibilityStatus.ELIGIBILITY_GATED


def test_visa_sponsorship_flag_wins_over_offshore_location() -> None:
    result = assess_eligibility("Toronto, Canada", is_remote=False, visa_sponsorship=True)
    assert result.status is EligibilityStatus.ACTIONABLE
