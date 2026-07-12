"""Manual ingestion trigger (the scheduler in Phase 7 calls the same service)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession, HttpClient
from app.schemas.ingestion import IngestionResult
from app.services.ingestion import IngestionService

router = APIRouter(prefix="/profiles/{profile_id}", tags=["ingestion"])


@router.post("/ingest", response_model=IngestionResult)
async def run_ingestion(
    profile_id: int, current_user: CurrentUser, session: DBSession, http: HttpClient
) -> IngestionResult:
    """Run the search→normalize→dedup→store pipeline now for this profile."""
    return await IngestionService(session, http).run_profile(current_user.id, profile_id)
