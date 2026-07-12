"""The full run: search → normalize → expiry → dedup → match → store → notify (§14).

One place where the stages are chained, so the manual HTTP trigger and the scheduled
Celery task can never drift apart. Per-user locking lives in the scheduler (that's where
concurrent runs actually arise), not here.
"""

from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SearchMode
from app.schemas.pipeline import PipelineResult
from app.services.ingestion import IngestionService
from app.services.matching import MatchingService
from app.services.notification import NotificationService


class PipelineService:
    def __init__(self, session: AsyncSession, http: httpx.AsyncClient) -> None:
        self.session = session
        self.http = http

    async def run_profile(
        self, user_id: int, profile_id: int, mode: SearchMode = SearchMode.DAILY
    ) -> PipelineResult:
        ingestion = await IngestionService(self.session, self.http).run_profile(
            user_id, profile_id, mode=mode
        )
        matching = await MatchingService(self.session, self.http).run_profile(user_id, profile_id)
        notification = await NotificationService(self.session, self.http).notify_profile(
            user_id, profile_id
        )
        return PipelineResult(
            profile_id=profile_id,
            mode=mode,
            ingestion=ingestion,
            matching=matching,
            notification=notification,
        )
