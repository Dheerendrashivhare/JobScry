"""Resume repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Resume


class ResumeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, resume_id: int, profile_id: int) -> Resume | None:
        result = await self.session.execute(
            select(Resume).where(Resume.id == resume_id, Resume.profile_id == profile_id)
        )
        return result.scalar_one_or_none()

    async def list_for_profile(self, profile_id: int, limit: int, offset: int) -> Sequence[Resume]:
        result = await self.session.execute(
            select(Resume)
            .where(Resume.profile_id == profile_id)
            .order_by(Resume.id)
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def count_for_profile(self, profile_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Resume).where(Resume.profile_id == profile_id)
        )
        return int(result.scalar_one())

    async def clear_primary(self, profile_id: int) -> None:
        await self.session.execute(
            update(Resume).where(Resume.profile_id == profile_id).values(is_primary=False)
        )

    def add(self, resume: Resume) -> None:
        self.session.add(resume)

    async def delete(self, resume: Resume) -> None:
        await self.session.delete(resume)
