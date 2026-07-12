"""Seen-job (per-profile dedup store) repository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SeenJob


class SeenJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def existing_keys(self, profile_id: int, dedup_keys: Sequence[str]) -> set[str]:
        if not dedup_keys:
            return set()
        result = await self.session.execute(
            select(SeenJob.dedup_key).where(
                SeenJob.profile_id == profile_id,
                SeenJob.dedup_key.in_(list(dedup_keys)),
            )
        )
        return set(result.scalars().all())

    def add(self, seen: SeenJob) -> None:
        self.session.add(seen)

    async def mark_notified(self, profile_id: int, job_ids: Sequence[int], when: datetime) -> None:
        """Stamp the dedup store so a job is never notified twice (§6, §7)."""
        if not job_ids:
            return
        await self.session.execute(
            update(SeenJob)
            .where(SeenJob.profile_id == profile_id, SeenJob.job_id.in_(list(job_ids)))
            .values(notified_at=when)
        )
