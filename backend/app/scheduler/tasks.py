"""Celery tasks (§14).

Celery workers are sync; the services are async — each task therefore owns an event loop
(``asyncio.run``) and its own DB session and HTTP client. Nothing is shared across tasks.

The scheduled fan-out enumerates active users' profiles that actually have an active
search, so an unconfigured profile never triggers a pointless provider run (§4).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from sqlalchemy import select

from app.database.session import get_sessionmaker
from app.models import Profile, Search, User
from app.models.enums import SearchMode
from app.scheduler.celery_app import celery_app
from app.scheduler.locks import UserLockBusy, user_lock
from app.services.pipeline import PipelineService


def _http() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "AJH/0.1 (+job-hunter)"})


async def _run_pipeline(user_id: int, profile_id: int, mode: SearchMode) -> dict[str, Any]:
    async with user_lock(user_id):
        async with _http() as http, get_sessionmaker()() as session:
            result = await PipelineService(session, http).run_profile(user_id, profile_id, mode)
            return result.model_dump(mode="json")


@celery_app.task(name="ajh.run_profile_pipeline", bind=True, max_retries=2)
def run_profile_pipeline(
    self: Any, user_id: int, profile_id: int, mode: str = SearchMode.DAILY.value
) -> dict[str, Any]:
    """Full run for one profile. Skips (does not fail) when the user is already running."""
    try:
        return asyncio.run(_run_pipeline(user_id, profile_id, SearchMode(mode)))
    except UserLockBusy as exc:
        # Not an error — another run holds the lock. Don't retry-storm it.
        return {"skipped": True, "reason": str(exc), "profile_id": profile_id}


async def _active_profile_targets() -> list[tuple[int, int]]:
    async with get_sessionmaker()() as session:
        result = await session.execute(
            select(Profile.user_id, Profile.id)
            .join(User, User.id == Profile.user_id)
            .join(Search, Search.profile_id == Profile.id)
            .where(User.is_active.is_(True), Search.is_active.is_(True))
            .distinct()
        )
        return [(int(user_id), int(profile_id)) for user_id, profile_id in result.all()]


@celery_app.task(name="ajh.dispatch_daily_pipelines")
def dispatch_daily_pipelines() -> dict[str, Any]:
    """Beat entry point: fan out one daily run per configured profile."""
    targets = asyncio.run(_active_profile_targets())
    for user_id, profile_id in targets:
        run_profile_pipeline.delay(user_id, profile_id, SearchMode.DAILY.value)
    return {"dispatched": len(targets)}
