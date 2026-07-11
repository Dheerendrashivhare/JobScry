"""Enumerations shared across ORM models.

All are ``str``-backed so values persist as readable strings and serialize cleanly
through Pydantic DTOs. Stored as VARCHAR + CHECK (see ``database.base.enum_column``).
"""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"


class WorkMode(str, enum.Enum):
    REMOTE = "remote"
    ONSITE = "onsite"
    HYBRID = "hybrid"


class ResumeFormat(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"
    LATEX = "latex"


class ResumeParseStatus(str, enum.Enum):
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"


class ProviderSlug(str, enum.Enum):
    ADZUNA = "adzuna"
    JOOBLE = "jooble"
    JSEARCH = "jsearch"
    REMOTIVE = "remotive"
    GREENHOUSE_LEVER = "greenhouse_lever"
    SERPAPI_GOOGLE_JOBS = "serpapi_google_jobs"
    APIFY_LINKEDIN = "apify_linkedin"
    APIFY_NAUKRI = "apify_naukri"


class ProviderHealthStatus(str, enum.Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class CredentialKey(str, enum.Enum):
    """Secrets stored per-user, encrypted at rest with Fernet (CLAUDE.md §15)."""

    APIFY_TOKEN = "apify_token"
    LLM_API_KEY = "llm_api_key"
    SERPAPI_KEY = "serpapi_key"
    RAPIDAPI_KEY = "rapidapi_key"
    ADZUNA_APP_ID = "adzuna_app_id"
    ADZUNA_APP_KEY = "adzuna_app_key"
    JOOBLE_KEY = "jooble_key"
    TELEGRAM_BOT_TOKEN = "telegram_bot_token"
    SMTP_PASSWORD = "smtp_password"


class LLMProvider(str, enum.Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class SearchMode(str, enum.Enum):
    """Pipeline windows (CLAUDE.md §14)."""

    DAILY = "daily"  # last 24h
    CATCHUP = "catchup"  # last 3-7 days


class MatchBand(str, enum.Enum):
    """Score bands (CLAUDE.md §7). Gate is >=90."""

    HIGH = "high"  # 95-100
    MEDIUM_HIGH = "medium_high"  # 92-94
    STRETCH = "stretch"  # 90-91


class EligibilityStatus(str, enum.Enum):
    """Work-authorization outcome (CLAUDE.md §8)."""

    ACTIONABLE = "actionable"
    ELIGIBILITY_GATED = "eligibility_gated"


class ApplicationStatus(str, enum.Enum):
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class NotificationChannel(str, enum.Enum):
    TELEGRAM = "telegram"
    EMAIL = "email"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
