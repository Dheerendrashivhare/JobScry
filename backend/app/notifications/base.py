"""Notifier contract + the rendered digest that flows through it (CLAUDE.md §13).

Telegram and Email only. A notifier's job is delivery — deciding *what* to send (the
top-20 fresh cap, the never-repeat rule) belongs to the notification service, not here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.enums import NotificationChannel


class NotificationError(Exception):
    """Delivery failed. Recorded on the Notification row; the run continues."""


@dataclass(frozen=True)
class Digest:
    subject: str
    text: str  # plain text (Telegram / email fallback)
    html: str  # email body


class Notifier(ABC):
    channel: NotificationChannel

    @abstractmethod
    async def send(self, digest: Digest) -> None:
        """Deliver the digest, or raise NotificationError."""
