"""Matching API tests: ingest → score → gate → list, over the ASGI app.

Provider HTTP is mocked, so the two ingested jobs are deterministic: one is a genuine
fit that clears the 90 gate, one is a near-miss that must NOT be inflated to reach it.
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
            "description": "Python and FastAPI backend work. 3-5 years experience required.",
            "salary": "₹18 LPA",
            "publication_date": "2026-07-10T00:00:00",
            "tags": ["Python", "FastAPI"],
        },
        {
            "id": 2,
            "url": "https://remotive.com/remote-jobs/python-2",
            "title": "Python Developer",
            "company_name": "Globex",
            "candidate_required_location": "India",
            "description": "General API work.",
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
async def client() -> AsyncIterator[AsyncClient]:
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


async def _auth(ac: AsyncClient) -> dict[str, str]:
    await ac.post(
        f"{API}/auth/register",
        json={"email": "o@e.com", "password": "supersecret", "full_name": None},
    )
    token = (
        await ac.post(f"{API}/auth/login", json={"email": "o@e.com", "password": "supersecret"})
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _profile_with_skills(ac: AsyncClient, headers: dict[str, str]) -> int:
    resp = await ac.post(
        f"{API}/profiles",
        json={
            "name": "Backend — India",
            "target_roles": ["Backend Engineer", "Python Developer"],
            "locations": ["India"],
            "experience_min_years": 2,
            "experience_max_years": 5,
            "skills": [
                {"name": "Python", "is_required": True},
                {"name": "FastAPI", "is_required": True},
            ],
        },
        headers=headers,
    )
    return int(resp.json()["id"])


async def _ingest(ac: AsyncClient, headers: dict[str, str], profile_id: int) -> None:
    await ac.post(
        f"{API}/profiles/{profile_id}/searches",
        json={"name": "remotive", "provider_slug": "remotive", "params": {}},
        headers=headers,
    )
    await ac.post(f"{API}/profiles/{profile_id}/ingest", headers=headers)


async def test_scores_gate_and_never_inflates(client: AsyncClient) -> None:
    headers = await _auth(client)
    profile_id = await _profile_with_skills(client, headers)
    await _ingest(client, headers, profile_id)

    resp = await client.post(f"{API}/profiles/{profile_id}/match", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["evaluated"] == 2
    # The strong fit clears the gate; the near-miss is reported honestly, not promoted.
    assert body["qualified"] == 1
    assert body["below_gate"] == 1
    assert body["llm_enabled"] is False  # no LLM key -> explanations disabled (§2)
    assert body["explanations_generated"] == 0

    listed = await client.get(f"{API}/profiles/{profile_id}/matches", headers=headers)
    assert listed.status_code == 200
    matches = listed.json()["items"]
    assert len(matches) == 1

    match = matches[0]
    assert match["score"] >= 90
    assert match["band"] in {"high", "medium_high", "stretch"}
    assert match["eligibility_status"] == "actionable"  # India role (§8)
    assert match["job"]["company"] == "Acme"
    assert set(match["strengths"]) == {"python", "fastapi"}
    assert match["explanation"] is None  # no LLM key
    assert match["recommendation"]  # deterministic, always present
    assert match["component_scores"]["tech_stack"] == 100


async def test_rerun_does_not_duplicate_matches(client: AsyncClient) -> None:
    headers = await _auth(client)
    profile_id = await _profile_with_skills(client, headers)
    await _ingest(client, headers, profile_id)

    first = await client.post(f"{API}/profiles/{profile_id}/match", headers=headers)
    assert first.json()["qualified"] == 1

    # Re-run: the already-matched job is skipped. The below-gate job carries no Match
    # row (only qualified jobs are stored), so it is simply re-scored — deterministically
    # to the same result — and still doesn't qualify. No duplicates either way.
    second = await client.post(f"{API}/profiles/{profile_id}/match", headers=headers)
    assert second.json()["qualified"] == 0
    assert second.json()["below_gate"] == 1

    listed = await client.get(f"{API}/profiles/{profile_id}/matches", headers=headers)
    assert listed.json()["total"] == 1


async def test_empty_profile_is_refused_not_scored(client: AsyncClient) -> None:
    """§4 empty-state: ask the user, don't score a skill-less profile."""
    headers = await _auth(client)
    resp = await client.post(f"{API}/profiles", json={"name": "No skills yet"}, headers=headers)
    profile_id = resp.json()["id"]

    match = await client.post(f"{API}/profiles/{profile_id}/match", headers=headers)
    assert match.status_code == 422
    assert match.json()["code"] == "profile_incomplete"


async def test_matching_requires_owned_profile(client: AsyncClient) -> None:
    headers = await _auth(client)
    profile_id = await _profile_with_skills(client, headers)

    await client.post(
        f"{API}/auth/register",
        json={"email": "x@e.com", "password": "supersecret", "full_name": None},
    )
    other = (
        await client.post(f"{API}/auth/login", json={"email": "x@e.com", "password": "supersecret"})
    ).json()["access_token"]

    resp = await client.post(
        f"{API}/profiles/{profile_id}/match",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert resp.status_code == 404
