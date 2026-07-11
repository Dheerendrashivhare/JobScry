"""Saved-search use-cases (always scoped through the owning profile)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProfileNotFoundError, SearchNotFoundError
from app.models import Search
from app.repositories.profile import ProfileRepository
from app.repositories.search import SearchRepository
from app.schemas.common import Page, Pagination
from app.schemas.search import SearchCreate, SearchRead, SearchUpdate


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SearchRepository(session)
        self.profiles = ProfileRepository(session)

    async def _require_profile(self, user_id: int, profile_id: int) -> None:
        if await self.profiles.get_for_user(profile_id, user_id) is None:
            raise ProfileNotFoundError()

    async def _require_search(self, user_id: int, profile_id: int, search_id: int) -> Search:
        await self._require_profile(user_id, profile_id)
        search = await self.repo.get(search_id, profile_id)
        if search is None:
            raise SearchNotFoundError()
        return search

    async def create(self, user_id: int, profile_id: int, data: SearchCreate) -> SearchRead:
        await self._require_profile(user_id, profile_id)
        search = Search(
            profile_id=profile_id,
            name=data.name,
            provider_slug=data.provider_slug,
            mode=data.mode,
            is_active=data.is_active,
            params=data.params,
        )
        self.repo.add(search)
        await self.session.commit()
        await self.session.refresh(search)
        return SearchRead.model_validate(search)

    async def list(self, user_id: int, profile_id: int, page: Pagination) -> Page[SearchRead]:
        await self._require_profile(user_id, profile_id)
        items = await self.repo.list_for_profile(profile_id, page.limit, page.offset)
        total = await self.repo.count_for_profile(profile_id)
        return Page(
            items=[SearchRead.model_validate(s) for s in items],
            total=total,
            limit=page.limit,
            offset=page.offset,
        )

    async def get(self, user_id: int, profile_id: int, search_id: int) -> SearchRead:
        return SearchRead.model_validate(await self._require_search(user_id, profile_id, search_id))

    async def update(
        self, user_id: int, profile_id: int, search_id: int, data: SearchUpdate
    ) -> SearchRead:
        search = await self._require_search(user_id, profile_id, search_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(search, field, value)
        await self.session.commit()
        await self.session.refresh(search)
        return SearchRead.model_validate(search)

    async def delete(self, user_id: int, profile_id: int, search_id: int) -> None:
        search = await self._require_search(user_id, profile_id, search_id)
        await self.repo.delete(search)
        await self.session.commit()
