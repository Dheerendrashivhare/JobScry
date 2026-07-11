"""Settings use-cases. Settings are created lazily on first access."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserSettings
from app.repositories.settings import SettingsRepository
from app.schemas.settings import SettingsUpdate


class SettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SettingsRepository(session)

    async def get_or_create(self, user_id: int) -> UserSettings:
        settings = await self.repo.get_for_user(user_id)
        if settings is None:
            settings = UserSettings(user_id=user_id)
            self.repo.add(settings)
            await self.session.commit()
            await self.session.refresh(settings)
        return settings

    async def update(self, user_id: int, data: SettingsUpdate) -> UserSettings:
        settings = await self.get_or_create(user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(settings, field, value)
        await self.session.commit()
        await self.session.refresh(settings)
        return settings
