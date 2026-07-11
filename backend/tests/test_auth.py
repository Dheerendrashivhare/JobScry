"""Authentication API tests.

End-to-end over the ASGI app with an in-memory aiosqlite database swapped in via a
``get_db`` dependency override (fresh schema per test). Covers registration policy
(first user = Admin), login, JWT refresh, the current-user dependency, and RBAC.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  register metadata
from app.database.base import Base
from app.database.session import get_db
from app.main import create_app

API = "/api/v1"


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

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await engine.dispose()


async def _register(
    client: AsyncClient,
    email: str = "owner@example.com",
    password: str = "supersecret",
    full_name: str | None = None,
) -> object:
    return await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )


async def _login(client: AsyncClient, email: str, password: str) -> object:
    return await client.post(f"{API}/auth/login", json={"email": email, "password": password})


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- registration -----------------------------------------------------------


async def test_first_user_becomes_admin(client: AsyncClient) -> None:
    resp = await _register(client, "admin@example.com")
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "admin"
    assert body["email"] == "admin@example.com"
    assert "password" not in body and "hashed_password" not in body


async def test_second_user_is_regular_user(client: AsyncClient) -> None:
    await _register(client, "admin@example.com")
    resp = await _register(client, "friend@example.com")
    assert resp.status_code == 201
    assert resp.json()["role"] == "user"


async def test_duplicate_email_conflicts(client: AsyncClient) -> None:
    await _register(client, "dup@example.com")
    resp = await _register(client, "dup@example.com")
    assert resp.status_code == 409
    assert resp.json()["code"] == "email_already_exists"


async def test_short_password_is_rejected(client: AsyncClient) -> None:
    resp = await _register(client, "short@example.com", password="short")
    assert resp.status_code == 422


# --- login ------------------------------------------------------------------


async def test_login_returns_token_pair(client: AsyncClient) -> None:
    await _register(client, "user@example.com", "supersecret")
    resp = await _login(client, "user@example.com", "supersecret")
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]


async def test_login_wrong_password(client: AsyncClient) -> None:
    await _register(client, "user@example.com", "supersecret")
    resp = await _login(client, "user@example.com", "wrongpassword")
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_credentials"


async def test_login_unknown_email(client: AsyncClient) -> None:
    resp = await _login(client, "nobody@example.com", "supersecret")
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_credentials"


# --- current user / me ------------------------------------------------------


async def test_me_requires_authentication(client: AsyncClient) -> None:
    resp = await client.get(f"{API}/auth/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_token"


async def test_me_returns_current_user(client: AsyncClient) -> None:
    await _register(client, "user@example.com", "supersecret")
    token = (await _login(client, "user@example.com", "supersecret")).json()["access_token"]
    resp = await client.get(f"{API}/auth/me", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"


async def test_me_rejects_refresh_token(client: AsyncClient) -> None:
    await _register(client, "user@example.com", "supersecret")
    refresh = (await _login(client, "user@example.com", "supersecret")).json()["refresh_token"]
    resp = await client.get(f"{API}/auth/me", headers=_auth(refresh))
    assert resp.status_code == 401


# --- refresh ----------------------------------------------------------------


async def test_refresh_issues_working_access_token(client: AsyncClient) -> None:
    await _register(client, "user@example.com", "supersecret")
    refresh = (await _login(client, "user@example.com", "supersecret")).json()["refresh_token"]
    resp = await client.post(f"{API}/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    new_access = resp.json()["access_token"]
    me = await client.get(f"{API}/auth/me", headers=_auth(new_access))
    assert me.status_code == 200


async def test_refresh_rejects_access_token(client: AsyncClient) -> None:
    await _register(client, "user@example.com", "supersecret")
    access = (await _login(client, "user@example.com", "supersecret")).json()["access_token"]
    resp = await client.post(f"{API}/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401


# --- RBAC -------------------------------------------------------------------


async def test_admin_can_list_users(client: AsyncClient) -> None:
    await _register(client, "admin@example.com", "supersecret")  # first -> admin
    await _register(client, "friend@example.com", "supersecret")
    token = (await _login(client, "admin@example.com", "supersecret")).json()["access_token"]
    resp = await client.get(f"{API}/auth/users", headers=_auth(token))
    assert resp.status_code == 200
    assert {u["email"] for u in resp.json()} == {"admin@example.com", "friend@example.com"}


async def test_non_admin_forbidden_from_users(client: AsyncClient) -> None:
    await _register(client, "admin@example.com", "supersecret")  # first -> admin
    await _register(client, "friend@example.com", "supersecret")  # -> user
    token = (await _login(client, "friend@example.com", "supersecret")).json()["access_token"]
    resp = await client.get(f"{API}/auth/users", headers=_auth(token))
    assert resp.status_code == 403
    assert resp.json()["code"] == "insufficient_permissions"
