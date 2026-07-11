"""Profile repository. Eager-loads skills so async responses never lazy-load."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Profile, ProfileSkill


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _with_skills(self) -> Select[tuple[Profile]]:
        # populate_existing refreshes relationships on identity-map instances so a
        # read-after-write (e.g. add_skill) reflects the just-committed rows.
        return (
            select(Profile)
            .options(selectinload(Profile.profile_skills).selectinload(ProfileSkill.skill))
            .execution_options(populate_existing=True)
        )

    async def get_for_user(self, profile_id: int, user_id: int) -> Profile | None:
        result = await self.session.execute(
            self._with_skills().where(Profile.id == profile_id, Profile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: int, limit: int, offset: int) -> Sequence[Profile]:
        result = await self.session.execute(
            self._with_skills()
            .where(Profile.user_id == user_id)
            .order_by(Profile.id)
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def count_for_user(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Profile).where(Profile.user_id == user_id)
        )
        return int(result.scalar_one())

    async def clear_default(self, user_id: int) -> None:
        await self.session.execute(
            update(Profile).where(Profile.user_id == user_id).values(is_default=False)
        )

    def add(self, profile: Profile) -> None:
        self.session.add(profile)

    async def delete(self, profile: Profile) -> None:
        await self.session.delete(profile)
