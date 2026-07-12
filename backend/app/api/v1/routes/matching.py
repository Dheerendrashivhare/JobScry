"""Matching routes: run the scoring pass, list resulting matches."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession, HttpClient, PageParams
from app.core.exceptions import ProfileNotFoundError
from app.repositories.match import MatchRepository
from app.repositories.profile import ProfileRepository
from app.schemas.common import Page
from app.schemas.match import MatchingResult, MatchRead
from app.services.matching import MatchingService

router = APIRouter(prefix="/profiles/{profile_id}", tags=["matching"])


@router.post("/match", response_model=MatchingResult)
async def run_matching(
    profile_id: int, current_user: CurrentUser, session: DBSession, http: HttpClient
) -> MatchingResult:
    """Score every un-matched job seen by this profile. Honest counts, no inflation (§7)."""
    return await MatchingService(session, http).run_profile(current_user.id, profile_id)


@router.get("/matches", response_model=Page[MatchRead])
async def list_matches(
    profile_id: int, current_user: CurrentUser, session: DBSession, page: PageParams
) -> Page[MatchRead]:
    if await ProfileRepository(session).get_for_user(profile_id, current_user.id) is None:
        raise ProfileNotFoundError()

    repo = MatchRepository(session)
    items = await repo.list_for_profile(profile_id, page.limit, page.offset)
    total = await repo.count_for_profile(profile_id)
    return Page(
        items=[MatchRead.model_validate(m) for m in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
