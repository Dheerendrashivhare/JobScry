"""Match repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Job, JobSkill, Match, SeenJob
from app.models.enums import EligibilityStatus


class MatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _with_job(self) -> Select[tuple[Match]]:
        return (
            select(Match).options(selectinload(Match.job)).execution_options(populate_existing=True)
        )

    async def existing_job_ids(self, profile_id: int) -> set[int]:
        result = await self.session.execute(
            select(Match.job_id).where(Match.profile_id == profile_id)
        )
        return set(result.scalars().all())

    async def candidate_jobs(self, profile_id: int) -> Sequence[Job]:
        """Jobs surfaced to this profile (via seen_jobs) that aren't expired."""
        result = await self.session.execute(
            select(Job)
            .join(SeenJob, SeenJob.job_id == Job.id)
            .where(SeenJob.profile_id == profile_id, Job.is_expired.is_(False))
            .options(selectinload(Job.job_skills).selectinload(JobSkill.skill))
            .execution_options(populate_existing=True)
        )
        return result.scalars().unique().all()

    async def fresh_for_profile(self, profile_id: int, limit: int) -> Sequence[Match]:
        """Un-notified matches, actionable-now first, then best score (§7, §8)."""
        actionable_first = case(
            (Match.eligibility_status == EligibilityStatus.ACTIONABLE, 0), else_=1
        )
        result = await self.session.execute(
            self._with_job()
            .where(Match.profile_id == profile_id, Match.notified.is_(False))
            .order_by(actionable_first, Match.score.desc(), Match.id.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def list_for_profile(self, profile_id: int, limit: int, offset: int) -> Sequence[Match]:
        result = await self.session.execute(
            self._with_job()
            .where(Match.profile_id == profile_id)
            .order_by(Match.score.desc(), Match.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def count_for_profile(self, profile_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Match).where(Match.profile_id == profile_id)
        )
        return int(result.scalar_one())

    def add(self, match: Match) -> None:
        self.session.add(match)
