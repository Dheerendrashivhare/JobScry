"""Seen-job (per-profile dedup store) repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
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
