"""Email notifier — SMTP via the stdlib, run off the event loop.

``smtplib`` is blocking, so the send happens in a worker thread rather than stalling
the async pipeline. No extra dependency needed.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from app.models.enums import NotificationChannel
from app.notifications.base import Digest, NotificationError, Notifier


class EmailNotifier(Notifier):
    channel = NotificationChannel.EMAIL

    def __init__(
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        recipient: str,
        use_tls: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.recipient = recipient
        self.use_tls = use_tls

    async def send(self, digest: Digest) -> None:
        try:
            await asyncio.to_thread(self._send_blocking, digest)
        except (smtplib.SMTPException, OSError) as exc:
            raise NotificationError(f"Email send failed: {exc}") from exc

    def _send_blocking(self, digest: Digest) -> None:
        message = EmailMessage()
        message["Subject"] = digest.subject
        message["From"] = self.username or self.recipient
        message["To"] = self.recipient
        message.set_content(digest.text)
        message.add_alternative(digest.html, subtype="html")

        with smtplib.SMTP(self.host, self.port, timeout=30) as server:
            if self.use_tls:
                server.starttls()
            if self.username and self.password:
                server.login(self.username, self.password)
            server.send_message(message)
