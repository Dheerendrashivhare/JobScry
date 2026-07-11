"""Notification delivery log.

One row per send attempt (CLAUDE.md §13: Telegram + Email only). A single run
bundles up to the top-20 fresh matches; the ``payload`` records which match IDs were
included so repeats can be audited (never re-notify — §7).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, enum_column
from app.models.enums import NotificationChannel, NotificationStatus

if TYPE_CHECKING:
    from app.models.profile import Profile
    from app.models.user import User


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )

    channel: Mapped[NotificationChannel] = enum_column(NotificationChannel, nullable=False)
    status: Mapped[NotificationStatus] = enum_column(
        NotificationStatus, default=NotificationStatus.PENDING, nullable=False
    )
    subject: Mapped[str | None] = mapped_column(String(512))
    body: Mapped[str | None] = mapped_column(Text)
    # Included match IDs + any delivery metadata.
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="notifications")
    profile: Mapped[Profile | None] = relationship()
