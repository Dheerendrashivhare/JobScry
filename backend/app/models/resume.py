"""Resume model. Multiple per profile; PDF/DOCX/LaTeX only (CLAUDE.md §11)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, enum_column
from app.models.enums import ResumeFormat, ResumeParseStatus

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.profile import Profile


class Resume(Base, TimestampMixin):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[ResumeFormat] = enum_column(ResumeFormat, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text)

    parse_status: Mapped[ResumeParseStatus] = enum_column(
        ResumeParseStatus, default=ResumeParseStatus.PENDING, nullable=False
    )
    parse_error: Mapped[str | None] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)

    profile: Mapped[Profile] = relationship(back_populates="resumes")
    # Matches whose tailored resume points back here.
    tailored_matches: Mapped[list[Match]] = relationship(
        back_populates="tailored_resume", foreign_keys="Match.tailored_resume_id"
    )
