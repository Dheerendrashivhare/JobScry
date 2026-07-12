"""Versioned API router. Feature routers are attached here."""

from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    credentials,
    ingestion,
    matching,
    pipeline,
    profiles,
    providers,
    resumes,
    searches,
    settings,
)

api_router = APIRouter()


@api_router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


api_router.include_router(auth.router)
api_router.include_router(profiles.router)
api_router.include_router(searches.router)
api_router.include_router(resumes.router)
api_router.include_router(ingestion.router)
api_router.include_router(matching.router)
api_router.include_router(pipeline.router)
api_router.include_router(credentials.router)
api_router.include_router(settings.router)
api_router.include_router(providers.router)
