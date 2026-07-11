"""Declarative base, shared mixins, and portable column helpers.

Every ORM model inherits from :class:`Base`. A metadata naming convention keeps
constraint and index names deterministic so Alembic autogenerate yields stable,
reviewable migrations. Enum columns are stored as ``VARCHAR + CHECK`` (not native
PostgreSQL enums) so the schema also builds on SQLite for fast, driver-free model
tests, and so enum changes never require a native-type migration dance.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum as SAEnum, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic names for indexes and constraints (see Alembic docs).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base for all AJH models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` audit columns (UTC, DB-driven)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def enum_column(enum_cls: type[enum.Enum], **kwargs: Any) -> Mapped[Any]:
    """Portable, string-backed enum column.

    Uses ``native_enum=False`` so the value is a validated ``VARCHAR`` with a named
    CHECK constraint on every dialect. ``values_callable`` persists each member's
    lowercase ``.value`` (e.g. ``"user"``) rather than its name — matching the str
    enum definitions and how the value serializes through Pydantic DTOs. The explicit
    ``name`` feeds the metadata naming convention for a stable constraint name.
    """
    return mapped_column(
        SAEnum(
            enum_cls,
            native_enum=False,
            validate_strings=True,
            length=50,
            name=enum_cls.__name__.lower(),
            values_callable=lambda cls: [member.value for member in cls],
        ),
        **kwargs,
    )
