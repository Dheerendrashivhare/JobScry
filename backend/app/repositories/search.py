"""Saved-search repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Search


class SearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, search_id: int, profile_id: int) -> Search | None:
        result = await self.session.execute(
            select(Search).where(Search.id == search_id, Search.profile_id == profile_id)
        )
        return result.scalar_one_or_none()

    async def list_for_profile(self, profile_id: int, limit: int, offset: int) -> Sequence[Search]:
        result = await self.session.execute(
            select(Search)
            .where(Search.profile_id == profile_id)
            .order_by(Search.id)
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def count_for_profile(self, profile_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Search).where(Search.profile_id == profile_id)
        )
        return int(result.scalar_one())

    def add(self, search: Search) -> None:
        self.session.add(search)

    async def delete(self, search: Search) -> None:
        await self.session.delete(search)
