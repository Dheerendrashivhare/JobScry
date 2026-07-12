"""Pipeline + notification triggers.

``POST /run`` executes the same :class:`PipelineService` the Celery beat task runs, so a
manual catch-up and the nightly job can never diverge. Locking is the scheduler's job —
these routes are the owner pressing the button himself.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DBSession, HttpClient
from app.models.enums import SearchMode
from app.schemas.notification import NotificationResult
from app.schemas.pipeline import PipelineResult
from app.services.notification import NotificationService
from app.services.pipeline import PipelineService

router = APIRouter(prefix="/profiles/{profile_id}", tags=["pipeline"])


@router.post("/run", response_model=PipelineResult)
async def run_pipeline(
    profile_id: int,
    current_user: CurrentUser,
    session: DBSession,
    http: HttpClient,
    mode: Annotated[
        SearchMode, Query(description="daily = last 24h; catchup = last 7 days")
    ] = SearchMode.DAILY,
) -> PipelineResult:
    """Search → normalize → expiry → dedup → match → store → notify, for this profile."""
    return await PipelineService(session, http).run_profile(current_user.id, profile_id, mode)


@router.post("/notify", response_model=NotificationResult)
async def notify(
    profile_id: int, current_user: CurrentUser, session: DBSession, http: HttpClient
) -> NotificationResult:
    """Send the top-N fresh matches now. No minimum — an empty run sends nothing (§7)."""
    return await NotificationService(session, http).notify_profile(current_user.id, profile_id)
