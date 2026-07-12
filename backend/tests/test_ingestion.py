"""Ingestion pipeline test — full stack over the ASGI app with mocked provider HTTP.

Only Remotive (no credentials) is enabled, so the run is deterministic. External
calls are served by an httpx MockTransport injected via the ``get_http_client``
dependency override.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  register metadata
from app.api.deps import get_http_client
from app.database.base import Base
from app.database.session import get_db
from app.main import create_app

API = "/api/v1"

REMOTIVE_PAYLOAD = {
    "jobs": [
        {
            "id": 1,
            "url": "https://remotive.com/remote-jobs/backend-1",
            "title": "Backend Engineer",
            "company_name": "Acme",
            "candidate_required_location": "India",
            "description": "Python / FastAPI",
            "salary": "₹18 LPA",
            "publication_date": "2026-07-10T00:00:00",
            "tags": ["Python", "FastAPI"],
        },
        {
            "id": 2,
            "url": "https://remotive.com/remote-jobs/python-2",
            "title": "Python Developer",
            "company_name": "Globex",
            "candidate_required_location": "Remote",
            "description": "APIs",
            "salary": "competitive",
            "publication_date": "2026-07-10T00:00:00",
            "tags": [],
        },
    ]
}


def _handler(request: httpx.Request) -> httpx.Response:
    if "remotive.com" in request.url.host:
        return httpx.Response(200, json=REMOTIVE_PAYLOAD)
    return httpx.Response(404, json={})


@pytest_asyncio.fixture
async def ingest_client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(_handler))

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def override_http() -> AsyncIterator[httpx.AsyncClient]:
        yield mock_http

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_http_client] = override_http
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await mock_http.aclose()
    await engine.dispose()


async def _setup_profile_with_search(ac: AsyncClient) -> tuple[dict[str, str], int]:
    await ac.post(
        f"{API}/auth/register",
        json={"email": "o@e.com", "password": "supersecret", "full_name": None},
    )
    token = (
        await ac.post(f"{API}/auth/login", json={"email": "o@e.com", "password": "supersecret"})
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    profile = await ac.post(
        f"{API}/profiles",
        json={"name": "Backend", "target_roles": ["Backend Engineer"], "locations": ["India"]},
        headers=headers,
    )
    profile_id = profile.json()["id"]
    await ac.post(
        f"{API}/profiles/{profile_id}/searches",
        json={"name": "remotive daily", "provider_slug": "remotive", "params": {}},
        headers=headers,
    )
    return headers, profile_id


async def test_ingestion_stores_new_then_dedups(ingest_client: AsyncClient) -> None:
    ac = ingest_client
    headers, profile_id = await _setup_profile_with_search(ac)

    first = await ac.post(f"{API}/profiles/{profile_id}/ingest", headers=headers)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["candidates"] == 2
    assert body["new_jobs"] == 2
    assert body["searches_run"] == 1
    assert any(p["provider"] == "remotive" and p["healthy"] for p in body["providers"])

    # Provider health persisted on the catalog.
    providers = await ac.get(f"{API}/providers", headers=headers)
    remotive = next(p for p in providers.json() if p["slug"] == "remotive")
    assert remotive["last_health_status"] == "healthy"

    # Second run: everything already in seen_jobs -> nothing new.
    second = await ac.post(f"{API}/profiles/{profile_id}/ingest", headers=headers)
    assert second.json()["candidates"] == 2
    assert second.json()["new_jobs"] == 0


async def test_ingestion_requires_owned_profile(ingest_client: AsyncClient) -> None:
    ac = ingest_client
    headers, profile_id = await _setup_profile_with_search(ac)
    await ac.post(
        f"{API}/auth/register",
        json={"email": "intruder@e.com", "password": "supersecret", "full_name": None},
    )
    other = (
        await ac.post(
            f"{API}/auth/login", json={"email": "intruder@e.com", "password": "supersecret"}
        )
    ).json()["access_token"]
    resp = await ac.post(
        f"{API}/profiles/{profile_id}/ingest",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert resp.status_code == 404
