"""Versioned API router. Feature routers are attached here."""

from fastapi import APIRouter

from app.api.v1.routes import auth

api_router = APIRouter()


@api_router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


api_router.include_router(auth.router)
