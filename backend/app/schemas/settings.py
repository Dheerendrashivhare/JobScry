"""User settings DTOs (notifications, LLM choice, UI prefs)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import LLMProvider


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    llm_provider: LLMProvider | None
    telegram_enabled: bool
    telegram_chat_id: str | None
    email_enabled: bool
    notify_email: str | None
    smtp_host: str | None
    smtp_port: int | None
    smtp_username: str | None
    notify_cap: int
    locale: str
    theme: str


class SettingsUpdate(BaseModel):
    """Partial update — only provided fields change."""

    llm_provider: LLMProvider | None = None
    telegram_enabled: bool | None = None
    telegram_chat_id: str | None = Field(default=None, max_length=64)
    email_enabled: bool | None = None
    notify_email: EmailStr | None = None
    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_username: str | None = Field(default=None, max_length=255)
    notify_cap: int | None = Field(default=None, ge=1, le=100)
    locale: str | None = Field(default=None, max_length=8)
    theme: str | None = Field(default=None, max_length=16)
