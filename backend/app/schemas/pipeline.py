"""Full-pipeline run DTO."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import SearchMode
from app.schemas.ingestion import IngestionResult
from app.schemas.match import MatchingResult
from app.schemas.notification import NotificationResult


class PipelineResult(BaseModel):
    profile_id: int
    mode: SearchMode
    ingestion: IngestionResult
    matching: MatchingResult
    notification: NotificationResult
