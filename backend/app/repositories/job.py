"""Job catalog repository (global, deduped on dedup_key)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_dedup_key(self, dedup_key: str) -> Job | None:
        result = await self.session.execute(select(Job).where(Job.dedup_key == dedup_key))
        return result.scalar_one_or_none()

    async def get_by_dedup_keys(self, dedup_keys: Sequence[str]) -> dict[str, Job]:
        if not dedup_keys:
            return {}
        result = await self.session.execute(select(Job).where(Job.dedup_key.in_(list(dedup_keys))))
        return {job.dedup_key: job for job in result.scalars().all()}

    def add(self, job: Job) -> None:
        self.session.add(job)
