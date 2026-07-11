"""Application-level exceptions and their HTTP mapping.

Services and the domain raise these instead of ``fastapi.HTTPException`` so business
logic stays free of presentation concerns (CLAUDE.md §3). A single handler,
registered on the app, renders them as ``{"detail", "code"}`` JSON responses.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class for expected, client-facing application errors."""

    status_code: int = 400
    code: str = "app_error"
    detail: str = "Application error"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class EmailAlreadyExistsError(AppError):
    status_code = 409
    code = "email_already_exists"
    detail = "Email already registered"


class InvalidCredentialsError(AppError):
    status_code = 401
    code = "invalid_credentials"
    detail = "Incorrect email or password"


class InactiveUserError(AppError):
    status_code = 403
    code = "inactive_user"
    detail = "User account is inactive"


class InvalidTokenError(AppError):
    status_code = 401
    code = "invalid_token"
    detail = "Could not validate credentials"


class InsufficientPermissionsError(AppError):
    status_code = 403
    code = "insufficient_permissions"
    detail = "Not enough permissions"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "code": exc.code},
            headers=headers,
        )
