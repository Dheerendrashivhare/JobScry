"""Notification use-case (CLAUDE.md §7, §13).

The rules that matter and are enforced here, not in the adapters:

* **Cap = top 20 fresh matches per run, and there is NO minimum.** If a run produces
  three matches, three are sent. We never pad the digest to look busier.
* **Never repeat.** A match is marked notified only after a channel actually accepted
  it, so a failed send retries next run rather than silently swallowing the job.
* Actionable-now roles lead; eligibility-gated ones follow and are labelled as such (§8).
* Telegram + Email only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProfileNotFoundError
from app.models import Match, Notification, UserSettings
from app.models.enums import CredentialKey, EligibilityStatus, NotificationStatus
from app.notifications.base import Digest, NotificationError, Notifier
from app.notifications.email import EmailNotifier
from app.notifications.telegram import TelegramNotifier
from app.repositories.match import MatchRepository
from app.repositories.profile import ProfileRepository
from app.repositories.seen_job import SeenJobRepository
from app.schemas.notification import ChannelResult, NotificationResult
from app.services.credential import CredentialService
from app.services.settings import SettingsService


def _line(match: Match) -> str:
    job = match.job
    bits = [f"[{match.score}] {job.title} — {job.company}"]
    if job.location:
        bits.append(f"  {job.location}")
    if job.salary_raw:
        bits.append(f"  {job.salary_raw}")
    if match.eligibility_status is EligibilityStatus.ELIGIBILITY_GATED:
        bits.append("  ⚠ eligibility-gated: no stated sponsorship — ask the recruiter")
    bits.append(f"  {job.apply_url or job.url}")
    return "\n".join(bits)


def render_digest(profile_name: str, matches: list[Match]) -> Digest:
    count = len(matches)
    subject = f"AJH — {count} new match{'es' if count != 1 else ''} for {profile_name}"

    header = (
        f"{count} new match{'es' if count != 1 else ''} for {profile_name}.\n"
        "Scored ≥ your gate. Nothing padded — this is the honest count.\n"
    )
    text = header + "\n" + "\n\n".join(_line(m) for m in matches)

    rows = []
    for match in matches:
        job = match.job
        gated = (
            '<div style="color:#b45309">⚠ eligibility-gated — no stated sponsorship; '
            "ask the recruiter</div>"
            if match.eligibility_status is EligibilityStatus.ELIGIBILITY_GATED
            else ""
        )
        explanation = (
            f'<div style="color:#555">{escape(match.explanation)}</div>'
            if match.explanation
            else ""
        )
        rows.append(
            "<li style='margin-bottom:14px'>"
            f"<b>{match.score}</b> — "
            f'<a href="{escape(job.apply_url or job.url)}">{escape(job.title)}</a>'
            f" — {escape(job.company)}"
            f"<div>{escape(job.location or '')} {escape(job.salary_raw or '')}</div>"
            f"{gated}{explanation}"
            "</li>"
        )
    html = (
        f"<p>{escape(header)}</p><ul style='list-style:none;padding:0'>" + "".join(rows) + "</ul>"
    )
    return Digest(subject=subject, text=text, html=html)


class NotificationService:
    def __init__(self, session: AsyncSession, http: httpx.AsyncClient) -> None:
        self.session = session
        self.http = http
        self.matches = MatchRepository(session)
        self.profiles = ProfileRepository(session)
        self.seen = SeenJobRepository(session)

    async def notify_profile(self, user_id: int, profile_id: int) -> NotificationResult:
        profile = await self.profiles.get_for_user(profile_id, user_id)
        if profile is None:
            raise ProfileNotFoundError()

        settings = await SettingsService(self.session).get_or_create(user_id)
        fresh = list(await self.matches.fresh_for_profile(profile_id, settings.notify_cap))

        if not fresh:
            # No minimum (§7) — an empty run is a legitimate outcome, not a failure.
            return NotificationResult(
                profile_id=profile_id, selected=0, channels=[], notified_match_ids=[]
            )

        notifiers = await self._build_notifiers(user_id, settings)
        digest = render_digest(profile.name, fresh)
        now = datetime.now(UTC)

        results: list[ChannelResult] = []
        delivered = False

        for notifier in notifiers:
            record = Notification(
                user_id=user_id,
                profile_id=profile_id,
                channel=notifier.channel,
                subject=digest.subject,
                body=digest.text,
                payload={"match_ids": [m.id for m in fresh]},
            )
            try:
                await notifier.send(digest)
            except NotificationError as exc:
                record.status = NotificationStatus.FAILED
                record.error = str(exc)[:1000]
                results.append(
                    ChannelResult(channel=notifier.channel, sent=False, error=str(exc)[:200])
                )
            else:
                record.status = NotificationStatus.SENT
                record.sent_at = now
                delivered = True
                results.append(ChannelResult(channel=notifier.channel, sent=True, error=None))
            self.session.add(record)

        notified_ids: list[int] = []
        if delivered:
            # Only burn the "never repeat" flag once something actually went out.
            for match in fresh:
                match.notified = True
            notified_ids = [m.id for m in fresh]
            await self.seen.mark_notified(profile_id, [m.job_id for m in fresh], now)

        await self.session.commit()
        return NotificationResult(
            profile_id=profile_id,
            selected=len(fresh),
            channels=results,
            notified_match_ids=notified_ids,
        )

    async def _build_notifiers(self, user_id: int, settings: UserSettings) -> list[Notifier]:
        """A channel is only built when it is enabled AND its secret is present."""
        creds = CredentialService(self.session)
        notifiers: list[Notifier] = []

        if settings.telegram_enabled and settings.telegram_chat_id:
            token = await creds.get_secret(user_id, CredentialKey.TELEGRAM_BOT_TOKEN)
            if token:
                notifiers.append(TelegramNotifier(self.http, token, settings.telegram_chat_id))

        if settings.email_enabled and settings.notify_email and settings.smtp_host:
            password = await creds.get_secret(user_id, CredentialKey.SMTP_PASSWORD)
            notifiers.append(
                EmailNotifier(
                    host=settings.smtp_host,
                    port=settings.smtp_port or 587,
                    username=settings.smtp_username,
                    password=password,
                    recipient=settings.notify_email,
                )
            )
        return notifiers
