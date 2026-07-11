"""Resume DTOs. File bytes come in via multipart; only metadata comes out."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ResumeFormat, ResumeParseStatus


class ResumeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int
    filename: str
    format: ResumeFormat
    parse_status: ResumeParseStatus
    parse_error: str | None
    is_primary: bool
    created_at: datetime


class ResumeUpdate(BaseModel):
    is_primary: bool
