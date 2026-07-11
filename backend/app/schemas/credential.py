"""Credential DTOs. Plaintext secrets go in on write; only masked hints come out."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CredentialKey


class CredentialSet(BaseModel):
    key: CredentialKey
    value: str = Field(min_length=1, max_length=4096)


class CredentialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: CredentialKey
    masked_value: str
    updated_at: datetime
