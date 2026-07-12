"""Matching use-case: score → gate → eligibility → store (CLAUDE.md §7, §8, §9).

Order matters and encodes the integrity rule: the deterministic engine scores first
and the gate is applied to that score alone. Only afterwards may the LLM add prose.
An LLM failure (or a missing key) degrades to "no explanation" — never to a changed
score, and never to a job silently appearing or disappearing.

Empty-state rule (§4): a profile with no skills cannot be scored honestly, so we stop
and tell the user instead of running the pipeline on an empty profile.
"""

from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProfileIncompleteError, ProfileNotFoundError
from app.matching.eligibility import assess_eligibility
from app.matching.llm import LLMClient, LLMConfig, LLMError
from app.matching.scoring import ScoreInput, ScoreResult, score_job
from app.models import Job, Match, Profile
from app.models.enums import CredentialKey, EligibilityStatus, MatchBand
from app.repositories.match import MatchRepository
from app.repositories.profile import ProfileRepository
from app.schemas.match import MatchingResult
from app.services.credential import CredentialService
from app.services.settings import SettingsService


def _recommendation(band: MatchBand, eligibility: EligibilityStatus) -> str:
    if eligibility is EligibilityStatus.ELIGIBILITY_GATED:
        return (
            "Eligibility-gated: you are not work-authorised here and the posting does not "
            "offer sponsorship. Raise the eligibility question with the recruiter rather "
            "than declaring eligibility you don't have."
        )
    if band is MatchBand.HIGH:
        return "Strong fit — apply now, directly if possible."
    if band is MatchBand.MEDIUM_HIGH:
        return "Good fit — apply, and lead with the matching stack."
    return "Stretch — apply only if the role genuinely interests you."


class MatchingService:
    def __init__(self, session: AsyncSession, http: httpx.AsyncClient) -> None:
        self.session = session
        self.http = http
        self.repo = MatchRepository(session)
        self.profiles = ProfileRepository(session)

    async def run_profile(self, user_id: int, profile_id: int) -> MatchingResult:
        profile = await self.profiles.get_for_user(profile_id, user_id)
        if profile is None:
            raise ProfileNotFoundError()
        if not profile.profile_skills:
            raise ProfileIncompleteError(
                "This profile has no skills. Add skills before running matching — "
                "scoring an empty profile would be meaningless."
            )

        already_matched = await self.repo.existing_job_ids(profile_id)
        candidates = [
            job
            for job in await self.repo.candidate_jobs(profile_id)
            if job.id not in already_matched
        ]

        llm = await self._build_llm(user_id)
        qualified: list[tuple[Match, Job, ScoreResult]] = []
        below_gate = 0
        excluded_by_size = 0
        gated = 0

        for job in candidates:
            if self._excluded_by_company_size(profile, job):
                excluded_by_size += 1
                continue

            result = score_job(self._build_input(profile, job), min_score=profile.min_score)
            if result.band is None:
                below_gate += 1
                continue

            eligibility = assess_eligibility(
                location=job.location,
                is_remote=job.is_remote,
                description=job.description,
                visa_sponsorship=job.visa_sponsorship,
            )
            if eligibility.status is EligibilityStatus.ELIGIBILITY_GATED:
                gated += 1

            match = Match(
                profile_id=profile_id,
                job_id=job.id,
                score=result.score,
                band=result.band,
                eligibility_status=eligibility.status,
                component_scores=result.components,
                strengths=result.matched_skills,
                missing_skills=result.missing_skills,
                recommendation=_recommendation(result.band, eligibility.status),
            )
            self.repo.add(match)
            qualified.append((match, job, result))

        explanations = 0
        if llm is not None and qualified:
            settings = await SettingsService(self.session).get_or_create(user_id)
            # Bound LLM spend to the notification cap — explaining 500 jobs helps nobody.
            for match, job, result in qualified[: settings.notify_cap]:
                text = await self._explain(llm, profile, job, result)
                if text:
                    match.explanation = text
                    explanations += 1

        await self.session.commit()

        return MatchingResult(
            profile_id=profile_id,
            evaluated=len(candidates),
            qualified=len(qualified),
            below_gate=below_gate,
            excluded_by_company_size=excluded_by_size,
            eligibility_gated=gated,
            explanations_generated=explanations,
            llm_enabled=llm is not None,
        )

    def _excluded_by_company_size(self, profile: Profile, job: Job) -> bool:
        """Selection-odds mode (§9): narrow to small/mid companies when enabled."""
        if not profile.company_size_mode or profile.max_headcount is None:
            return False
        if job.company_headcount is None:
            return False  # unknown size — don't drop it on a guess
        return job.company_headcount > profile.max_headcount

    def _build_input(self, profile: Profile, job: Job) -> ScoreInput:
        profile_skills = {ps.skill.name: ps.weight for ps in profile.profile_skills}
        required = {ps.skill.name for ps in profile.profile_skills if ps.is_required}
        job_skills = {js.skill.name for js in job.job_skills}
        return ScoreInput(
            profile_skills=profile_skills,
            required_skills=required,
            target_roles=list(profile.target_roles),
            preferred_companies=list(profile.preferred_companies),
            ignored_companies=list(profile.ignored_companies),
            experience_min_years=profile.experience_min_years,
            experience_max_years=profile.experience_max_years,
            weights=dict(profile.scoring_weights),
            job_title=job.title,
            job_company=job.company,
            job_text=job.description or "",
            job_skills=job_skills,
            provider_slug=job.provider_slug,
            has_direct_apply=bool(job.apply_url),
            has_named_recruiter=bool(job.recruiter_name),
        )

    async def _build_llm(self, user_id: int) -> LLMClient | None:
        settings = await SettingsService(self.session).get_or_create(user_id)
        if settings.llm_provider is None:
            return None
        api_key = await CredentialService(self.session).get_secret(
            user_id, CredentialKey.LLM_API_KEY
        )
        if not api_key:
            return None  # no key -> scoring still works, explanations disabled (§2)
        return LLMClient(
            self.http,
            LLMConfig(provider=settings.llm_provider, api_key=api_key, model=settings.llm_model),
        )

    async def _explain(
        self, llm: LLMClient, profile: Profile, job: Job, result: ScoreResult
    ) -> str | None:
        all_skills = ", ".join(sorted(result.matched_skills + result.missing_skills))
        band = result.band.value if result.band else "none"
        prompt = (
            f"Candidate target roles: {', '.join(profile.target_roles) or 'n/a'}\n"
            f"Candidate experience: {profile.experience_min_years}-"
            f"{profile.experience_max_years or '?'} years\n"
            f"Candidate skills: {all_skills}\n\n"
            f"Job: {job.title} at {job.company} ({job.location or 'location n/a'})\n"
            f"Job description:\n{(job.description or '')[:4000]}\n\n"
            f"ALREADY-COMPUTED score: {result.score}/100 (band {band})\n"
            f"Component scores: {result.components}\n"
            f"Matched skills: {result.matched_skills}\n"
            f"Missing skills: {result.missing_skills}\n\n"
            "In 3-4 sentences, explain why this score is what it is. Do not restate a "
            "different number. Do not claim experience the candidate does not have."
        )
        try:
            return await llm.explain_match(prompt)
        except LLMError:
            return None  # degrade quietly; the score stands on its own
