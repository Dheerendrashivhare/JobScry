"""Notification-run DTOs."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import NotificationChannel


class ChannelResult(BaseModel):
    channel: NotificationChannel
    sent: bool
    error: str | None = None


class NotificationResult(BaseModel):
    """``selected`` is the honest count — there is no minimum (§7)."""

    profile_id: int
    selected: int
    channels: list[ChannelResult]
    notified_match_ids: list[int]
