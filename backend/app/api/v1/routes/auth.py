"""Authentication routes: register, login, refresh, me, users (admin)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import AdminUser, CurrentUser, DBSession
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, RefreshRequest, Token
from app.schemas.user import UserCreate, UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, session: DBSession) -> UserRead:
    """Create an account. The first-ever account becomes Admin; others are Users."""
    user = await AuthService(session).register(data)
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
async def login(data: LoginRequest, session: DBSession) -> Token:
    return await AuthService(session).login(data)


@router.post("/refresh", response_model=Token)
async def refresh(data: RefreshRequest, session: DBSession) -> Token:
    return await AuthService(session).refresh(data.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get("/users", response_model=list[UserRead])
async def list_users(_admin: AdminUser, session: DBSession) -> list[UserRead]:
    """Admin-only: list accounts (basic paging arrives with the Users API in Phase 4)."""
    users = await UserRepository(session).list()
    return [UserRead.model_validate(u) for u in users]
