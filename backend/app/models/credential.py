"""Per-user encrypted secrets (API keys, tokens).

Values are Fernet-encrypted before storage (CLAUDE.md §15, Phase-1 decision): the
DB only ever holds ciphertext. One row per (user, key). Encryption/decryption is
implemented in the security layer in a later phase; this model just persists the
ciphertext and never exposes plaintext.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, enum_column
from app.models.enums import CredentialKey

if TYPE_CHECKING:
    from app.models.user import User


class Credential(Base, TimestampMixin):
    __tablename__ = "credentials"
    __table_args__ = (UniqueConstraint("user_id", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    key: Mapped[CredentialKey] = enum_column(CredentialKey, nullable=False)
    # Fernet ciphertext (base64 text). Never store plaintext.
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped[User] = relationship(back_populates="credentials")
