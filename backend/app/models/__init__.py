"""ORM models package.

Importing this package registers every model on ``Base.metadata`` so that (a) the
SQLAlchemy mapper can resolve string-based relationships and (b) Alembic autogenerate
sees the full schema. Import order is chosen so dependencies resolve cleanly.
"""

from app.database.base import Base
from app.models.application import Application
from app.models.credential import Credential
from app.models.enums import (
    ApplicationStatus,
    CredentialKey,
    EligibilityStatus,
    LLMProvider,
    MatchBand,
    NotificationChannel,
    NotificationStatus,
    ProviderHealthStatus,
    ProviderSlug,
    ResumeFormat,
    ResumeParseStatus,
    SearchMode,
    UserRole,
    WorkMode,
)
from app.models.job import Job, JobSkill
from app.models.match import Match
from app.models.notification import Notification
from app.models.profile import DEFAULT_SCORING_WEIGHTS, Profile, ProfileSkill, Skill
from app.models.provider import Provider
from app.models.resume import Resume
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.models.settings import UserSettings
from app.models.user import User

__all__ = [
    "Base",
    # models
    "User",
    "Profile",
    "Skill",
    "ProfileSkill",
    "Resume",
    "Job",
    "JobSkill",
    "Match",
    "SeenJob",
    "Provider",
    "Credential",
    "UserSettings",
    "Search",
    "Application",
    "Notification",
    # constants
    "DEFAULT_SCORING_WEIGHTS",
    # enums
    "UserRole",
    "WorkMode",
    "ResumeFormat",
    "ResumeParseStatus",
    "ProviderSlug",
    "ProviderHealthStatus",
    "CredentialKey",
    "LLMProvider",
    "SearchMode",
    "MatchBand",
    "EligibilityStatus",
    "ApplicationStatus",
    "NotificationChannel",
    "NotificationStatus",
]
