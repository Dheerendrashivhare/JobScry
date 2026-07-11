"""ORM model tests.

Bound to an in-memory SQLite engine via a plain (sync) Session — no async driver
or Postgres needed. These validate that the mappers configure, relationships and
cascades behave, column defaults fire, and constraints are enforced. Postgres-level
concerns (native types, DB-side FK cascade) are exercised by the Alembic migration
and integration tests in later phases.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models import (
    DEFAULT_SCORING_WEIGHTS,
    Credential,
    Job,
    JobSkill,
    Profile,
    ProfileSkill,
    SeenJob,
    Skill,
    User,
    UserRole,
)

EXPECTED_TABLES = {
    "users",
    "profiles",
    "skills",
    "profile_skills",
    "resumes",
    "jobs",
    "job_skills",
    "matches",
    "providers",
    "applications",
    "notifications",
    "settings",
    "searches",
    "seen_jobs",
    "credentials",
}


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


def _make_user(session: Session, email: str = "owner@example.com") -> User:
    user = User(email=email, hashed_password="x")
    session.add(user)
    session.flush()
    return user


def test_all_expected_tables_registered() -> None:
    assert EXPECTED_TABLES <= set(Base.metadata.tables)


def test_schema_creates_on_sqlite(session: Session) -> None:
    tables = set(inspect(session.get_bind()).get_table_names())
    assert EXPECTED_TABLES <= tables


def test_profile_defaults_applied(session: Session) -> None:
    user = _make_user(session)
    profile = Profile(user=user, name="Backend — India")
    session.add(profile)
    session.commit()

    assert profile.scoring_weights == DEFAULT_SCORING_WEIGHTS
    # A copy, not the shared module-level dict.
    assert profile.scoring_weights is not DEFAULT_SCORING_WEIGHTS
    assert profile.min_score == 90
    assert profile.target_roles == []
    assert profile.is_default is False


def test_enum_persisted_as_string(session: Session) -> None:
    user = _make_user(session)
    session.commit()

    assert user.role is UserRole.USER
    stored = session.execute(text("SELECT role FROM users WHERE id = :i"), {"i": user.id}).scalar()
    assert stored == "user"


def test_user_profile_relationship(session: Session) -> None:
    user = _make_user(session)
    profile = Profile(user=user, name="Default")
    session.add(profile)
    session.commit()

    assert profile.user_id == user.id
    assert profile in user.profiles


def test_cascade_delete_orphans_children(session: Session) -> None:
    user = _make_user(session)
    profile = Profile(user=user, name="Default")
    session.add(profile)
    session.flush()
    session.add(SeenJob(profile=profile, dedup_key="https://example.com/job/1"))
    session.commit()

    session.delete(user)  # ORM cascade: profile -> seen_jobs
    session.commit()

    assert session.execute(select(Profile)).first() is None
    assert session.execute(select(SeenJob)).first() is None


def test_skill_shared_between_profile_and_job(session: Session) -> None:
    user = _make_user(session)
    profile = Profile(user=user, name="Default")
    skill = Skill(name="fastapi")
    job = Job(
        dedup_key="https://example.com/job/2",
        provider_slug="apify_linkedin",
        url="https://example.com/job/2",
        title="Backend Engineer",
        company="Acme",
    )
    session.add_all([profile, skill, job])
    session.flush()
    session.add(ProfileSkill(profile=profile, skill=skill, is_required=True))
    session.add(JobSkill(job=job, skill=skill))
    session.commit()

    assert skill.profile_skills[0].profile is profile
    assert skill.job_skills[0].job is job


def test_seen_job_dedup_key_unique_per_profile(session: Session) -> None:
    user = _make_user(session)
    profile = Profile(user=user, name="Default")
    session.add(profile)
    session.flush()
    session.add(SeenJob(profile=profile, dedup_key="dup"))
    session.commit()

    session.add(SeenJob(profile=profile, dedup_key="dup"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_credential_unique_per_user_key(session: Session) -> None:
    user = _make_user(session)
    session.add(Credential(user=user, key="apify_token", encrypted_value="cipher1"))
    session.commit()

    session.add(Credential(user=user, key="apify_token", encrypted_value="cipher2"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
