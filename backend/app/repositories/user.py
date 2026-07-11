"""User repository — the only place raw user queries live (CLAUDE.md §3)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(User))
        return int(result.scalar_one())

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[User]:
        result = await self.session.execute(
            select(User).order_by(User.id).limit(limit).offset(offset)
        )
        return result.scalars().all()

    def add(self, user: User) -> None:
        self.session.add(user)
