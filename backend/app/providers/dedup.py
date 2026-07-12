"""Dedup keys and expiry (CLAUDE.md §6).

Dedup is simple and URL/ID-based — no fuzzy cross-portal matching. A stable key is
derived by normalizing the listing URL (drop scheme/query/fragment/``www``, lowercase
host, strip trailing slash); when there is no usable URL we fall back to
``provider:external_id``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlsplit

from app.models.enums import ProviderSlug


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    candidate = url.strip()
    if not candidate:
        return None
    if "://" not in candidate:
        candidate = "https://" + candidate
    parts = urlsplit(candidate)
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/")
    if not host:
        return None
    return f"{host}{path}" if path else host


def make_dedup_key(
    url: str | None,
    external_id: str | None = None,
    provider: ProviderSlug | None = None,
) -> str:
    normalized = normalize_url(url)
    if normalized:
        return normalized
    if external_id and provider is not None:
        return f"{provider.value}:{external_id}"
    if external_id:
        return external_id
    raise ValueError("cannot build a dedup key without a URL or external id")


def is_expired(valid_through: datetime | None, now: datetime | None = None) -> bool:
    """True when a listing's validity window has passed. Unknown window → not expired."""
    if valid_through is None:
        return False
    reference = now or datetime.now(UTC)
    if valid_through.tzinfo is None:
        valid_through = valid_through.replace(tzinfo=UTC)
    return valid_through < reference
