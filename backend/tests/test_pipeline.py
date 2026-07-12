"""Phase 7-8: full pipeline (ingest → match → notify) over the ASGI app.

Provider HTTP and the Telegram Bot API are both served by an httpx MockTransport, so the
run is deterministic and nothing leaves the machine. The assertions target the rules that
are easy to get wrong: the ≥90 gate, the honest count (no minimum), and never-repeat.
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

# One job that should clear the gate, one that clearly should not.
REMOTIVE_PAYLOAD = {
    "jobs": [
        {
            "id": 1,
            "url": "https://remotive.com/remote-jobs/backend-1",
            "title": "Backend Engineer",
            "company_name": "Acme",
            "candidate_required_location": "India",
            "description": "Python, FastAPI and PostgreSQL. 3-5 years experience required.",
            "salary": "₹22 LPA",
            "publication_date": "2026-07-10T00:00:00",
            "tags": ["Python", "FastAPI", "PostgreSQL"],
        },
        {
            "id": 2,
            "url": "https://remotive.com/remote-jobs/ds-2",
            "title": "Data Scientist",
            "company_name": "Globex",
            "candidate_required_location": "India",
            "description": "R, TensorFlow and deep learning research. 10+ years experience.",
            "salary": "competitive",
            "publication_date": "2026-07-10T00:00:00",
            "tags": ["R", "TensorFlow"],
        },
    ]
}

telegram_sends: list[dict] = []


def _handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if "remotive.com" in host:
        return httpx.Response(200, json=REMOTIVE_PAYLOAD)
    if "api.telegram.org" in host:
        import json

        telegram_sends.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
    return httpx.Response(404, json={})


@pytest_asyncio.fixture
async def pipeline_client() -> AsyncIterator[AsyncClient]:
    telegram_sends.clear()
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


async def _setup(ac: AsyncClient, *, telegram: bool = True) -> tuple[dict[str, str], int]:
    await ac.post(
        f"{API}/auth/register",
        json={"email": "owner@e.com", "password": "supersecret", "full_name": None},
    )
    token = (
        await ac.post(f"{API}/auth/login", json={"email": "owner@e.com", "password": "supersecret"})
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    profile = await ac.post(
        f"{API}/profiles",
        json={
            "name": "Backend — India",
            "target_roles": ["Backend Engineer"],
            "locations": ["India"],
            "experience_min_years": 2,
            "experience_max_years": 5,
            "skills": [
                {"name": "Python", "is_required": True},
                {"name": "FastAPI", "is_required": True},
                {"name": "PostgreSQL"},
            ],
        },
        headers=headers,
    )
    profile_id = profile.json()["id"]

    await ac.post(
        f"{API}/profiles/{profile_id}/searches",
        json={"name": "remotive daily", "provider_slug": "remotive", "params": {}},
        headers=headers,
    )

    if telegram:
        await ac.patch(
            f"{API}/settings",
            json={"telegram_enabled": True, "telegram_chat_id": "4242"},
            headers=headers,
        )
        await ac.put(
            f"{API}/credentials",
            json={"key": "telegram_bot_token", "value": "bot-token-123"},
            headers=headers,
        )
    return headers, profile_id


async def test_full_pipeline_scores_gates_and_notifies(pipeline_client: AsyncClient) -> None:
    ac = pipeline_client
    headers, profile_id = await _setup(ac)

    resp = await ac.post(f"{API}/profiles/{profile_id}/run", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Ingestion picked up both listings.
    assert body["ingestion"]["new_jobs"] == 2

    # Only the genuine fit clears the >=90 gate — the other is reported, not inflated.
    matching = body["matching"]
    assert matching["evaluated"] == 2
    assert matching["qualified"] == 1
    assert matching["below_gate"] == 1
    assert matching["llm_enabled"] is False  # no LLM key -> scoring still works (§2)

    # Notification sends exactly the qualified one — no padding, no minimum.
    notification = body["notification"]
    assert notification["selected"] == 1
    assert len(notification["notified_match_ids"]) == 1
    assert any(c["channel"] == "telegram" and c["sent"] for c in notification["channels"])

    assert len(telegram_sends) == 1
    text = telegram_sends[0]["text"]
    assert "Backend Engineer" in text and "Acme" in text
    assert "Data Scientist" not in text  # below the gate — never notified


async def test_rerun_never_repeats_a_notified_job(pipeline_client: AsyncClient) -> None:
    ac = pipeline_client
    headers, profile_id = await _setup(ac)

    first = await ac.post(f"{API}/profiles/{profile_id}/run", headers=headers)
    assert first.json()["notification"]["selected"] == 1
    assert len(telegram_sends) == 1

    # Same listings come back; dedup + the notified flag mean nothing new goes out (§6, §7).
    second = await ac.post(f"{API}/profiles/{profile_id}/run", headers=headers)
    body = second.json()
    assert body["ingestion"]["new_jobs"] == 0  # dedup store suppresses both listings

    # The already-matched job is skipped. The below-gate one is deliberately re-scored:
    # only qualifying matches are persisted, so if the owner later adds a skill or retunes
    # the weights, a previously-rejected job gets reconsidered instead of being buried.
    assert body["matching"]["evaluated"] == 1
    assert body["matching"]["qualified"] == 0
    assert body["matching"]["below_gate"] == 1

    assert body["notification"]["selected"] == 0
    assert body["notification"]["notified_match_ids"] == []
    assert len(telegram_sends) == 1  # no second Telegram message


async def test_qualified_matches_are_listable(pipeline_client: AsyncClient) -> None:
    ac = pipeline_client
    headers, profile_id = await _setup(ac)
    await ac.post(f"{API}/profiles/{profile_id}/run", headers=headers)

    resp = await ac.get(f"{API}/profiles/{profile_id}/matches", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    match = body["items"][0]
    assert match["score"] >= 90
    assert match["band"] in {"high", "medium_high", "stretch"}
    assert match["eligibility_status"] == "actionable"  # India role (§8)
    assert match["job"]["company"] == "Acme"


async def test_no_notifier_configured_still_scores(pipeline_client: AsyncClient) -> None:
    """No Telegram/email set up: the run still ingests and scores, and sends nothing."""
    ac = pipeline_client
    headers, profile_id = await _setup(ac, telegram=False)

    body = (await ac.post(f"{API}/profiles/{profile_id}/run", headers=headers)).json()
    assert body["matching"]["qualified"] == 1
    assert body["notification"]["selected"] == 1
    assert body["notification"]["channels"] == []  # nothing to send through
    assert body["notification"]["notified_match_ids"] == []  # so not marked notified
    assert telegram_sends == []
