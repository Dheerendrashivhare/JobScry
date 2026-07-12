"""Match repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Job, JobSkill, Match, SeenJob


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
