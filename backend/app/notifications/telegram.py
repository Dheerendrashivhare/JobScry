"""Telegram notifier — Bot API sendMessage."""

from __future__ import annotations

import httpx

from app.models.enums import NotificationChannel
from app.notifications.base import Digest, NotificationError, Notifier

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
# Telegram hard-caps a message at 4096 chars.
_MAX_CHARS = 4000


class TelegramNotifier(Notifier):
    channel = NotificationChannel.TELEGRAM

    def __init__(self, http: httpx.AsyncClient, bot_token: str, chat_id: str) -> None:
        self.http = http
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(self, digest: Digest) -> None:
        body = digest.text
        if len(body) > _MAX_CHARS:
            body = body[:_MAX_CHARS].rsplit("\n", 1)[0] + "\n…(truncated)"
        payload = {
            "chat_id": self.chat_id,
            "text": body,
            "disable_web_page_preview": True,
        }
        try:
            resp = await self.http.post(
                TELEGRAM_API.format(token=self.bot_token), json=payload, timeout=30.0
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise NotificationError(f"Telegram send failed: {exc}") from exc

        data = resp.json()
        if not data.get("ok", False):
            raise NotificationError(f"Telegram rejected the message: {data.get('description')}")
