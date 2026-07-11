"""Shared test fixtures.

Provides an ASGI client bound to a fresh in-memory aiosqlite database (per test)
with the ``get_db`` dependency overridden. Test-only settings are injected via env
before any ``get_settings()`` call — safe because none of the imports below read
settings at import time (engine/secrets/crypto are all lazy).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  register metadata
from app.database.base import Base
from app.database.session import get_db
from app.main import create_app

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("CREDENTIALS_ENCRYPTION_KEY", "test-credentials-key")
os.environ.setdefault("RESUME_STORAGE_DIR", tempfile.mkdtemp(prefix="ajh-test-resumes-"))


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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await engine.dispose()
