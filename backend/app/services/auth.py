"""Authentication use-cases: register, login, refresh.

Owns the transaction boundary and enforces policy: the very first registered user
becomes Admin, everyone after is a User (owner decision, 2026-07-11). Raises domain
errors from ``core.exceptions`` — never HTTP exceptions (CLAUDE.md §3).
"""

from __future__ import annotations

import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.core.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import User, UserRole
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserCreate


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(self, data: UserCreate) -> User:
        email = data.email.lower()
        if await self.users.get_by_email(email) is not None:
            raise EmailAlreadyExistsError()

        # First account bootstraps the Admin; everyone after is a regular User.
        role = UserRole.ADMIN if await self.users.count() == 0 else UserRole.USER
        user = User(
            email=email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            role=role,
        )
        self.users.add(user)
        try:
            await self.session.commit()
        except IntegrityError as exc:  # unique(email) race
            await self.session.rollback()
            raise EmailAlreadyExistsError() from exc
        await self.session.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email.lower())
        # Same error whether the email is unknown or the password is wrong.
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()
        if not user.is_active:
            raise InactiveUserError()
        return user

    @staticmethod
    def issue_tokens(user: User) -> Token:
        return Token(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def login(self, data: LoginRequest) -> Token:
        user = await self.authenticate(data.email, data.password)
        return self.issue_tokens(user)

    async def refresh(self, refresh_token: str) -> Token:
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError as exc:
            raise InvalidTokenError() from exc
        if payload.get("type") != REFRESH_TOKEN_TYPE:
            raise InvalidTokenError("Invalid token type")
        subject = payload.get("sub")
        user = await self._load_active_user(subject)
        return self.issue_tokens(user)

    async def _load_active_user(self, subject: object) -> User:
        try:
            user_id = int(subject)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise InvalidTokenError() from exc
        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError()
        return user
