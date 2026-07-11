"""Skill repository — the canonical, case-insensitive skill vocabulary."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Skill


class SkillRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, name: str) -> Skill:
        # Normalize to lowercase so "FastAPI"/"fastapi" dedupe to one canonical row.
        normalized = name.strip().lower()
        result = await self.session.execute(select(Skill).where(Skill.name == normalized))
        skill = result.scalar_one_or_none()
        if skill is None:
            skill = Skill(name=normalized)
            self.session.add(skill)
            await self.session.flush()
        return skill
