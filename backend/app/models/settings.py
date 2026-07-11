"""Per-user application settings: notifications, LLM choice, UI prefs.

Secrets referenced here (bot token, SMTP password) live encrypted in
:class:`~app.models.credential.Credential`; this table holds only non-secret
configuration and delivery targets. Notifications are Telegram + Email only
(CLAUDE.md §13); the top-20 fresh cap is configurable via ``notify_cap`` (§7).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, enum_column
from app.models.enums import LLMProvider

if TYPE_CHECKING:
    from app.models.user import User


class UserSettings(Base, TimestampMixin):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # LLM (optional): no key -> scoring still works, tailoring/explanations off (§2).
    llm_provider: Mapped[LLMProvider | None] = enum_column(LLMProvider, nullable=True)

    # Telegram delivery.
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64))

    # Email delivery (SMTP host/user/port non-secret; password is a Credential).
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_email: Mapped[str | None] = mapped_column(String(320))
    smtp_host: Mapped[str | None] = mapped_column(String(255))
    smtp_port: Mapped[int | None] = mapped_column(Integer)
    smtp_username: Mapped[str | None] = mapped_column(String(255))

    # Notification cap per run (CLAUDE.md §7: top-20, no minimum).
    notify_cap: Mapped[int] = mapped_column(Integer, default=20, nullable=False)

    # UI (dark mode required, CLAUDE.md §2).
    locale: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    theme: Mapped[str] = mapped_column(String(16), default="dark", nullable=False)

    user: Mapped[User] = relationship(back_populates="settings")
