"""Reusable FastAPI dependencies: DB session, current user, RBAC guards."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InactiveUserError, InsufficientPermissionsError, InvalidTokenError
from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.database.session import get_db
from app.models import User, UserRole
from app.repositories.user import UserRepository

DBSession = Annotated[AsyncSession, Depends(get_db)]

# auto_error=False so a missing/short header yields our own 401 shape, not Starlette's.
_bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]


async def get_current_user(session: DBSession, credentials: BearerCredentials) -> User:
    if credentials is None:
        raise InvalidTokenError("Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise InvalidTokenError() from exc
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise InvalidTokenError("Invalid token type")
    subject = payload.get("sub")
    try:
        user_id = int(subject)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError() from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise InvalidTokenError()
    if not user.is_active:
        raise InactiveUserError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(current_user: CurrentUser) -> User:
    if current_user.role != UserRole.ADMIN:
        raise InsufficientPermissionsError()
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
