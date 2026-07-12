"""Small shared helpers for provider adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def parse_iso(value: Any) -> datetime | None:
    """Parse an ISO-8601 string (accepting a trailing ``Z``) into a datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def first_str(*values: Any) -> str:
    """First non-empty stringifiable value, else empty string."""
    for value in values:
        if value:
            return str(value)
    return ""
