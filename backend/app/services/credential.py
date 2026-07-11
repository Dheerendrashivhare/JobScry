"""Credential use-cases: encrypt on write, mask on read, delete.

Plaintext never leaves this layer except as a masked hint. Other services fetch the
decrypted value through :meth:`get_secret` when they actually need to call a provider.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import SecretDecryptionError, decrypt_secret, encrypt_secret, mask_secret
from app.core.exceptions import CredentialNotFoundError, SecretUnreadableError
from app.models import Credential
from app.models.enums import CredentialKey
from app.repositories.credential import CredentialRepository
from app.schemas.credential import CredentialRead, CredentialSet


class CredentialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CredentialRepository(session)

    async def set(self, user_id: int, data: CredentialSet) -> CredentialRead:
        ciphertext = encrypt_secret(data.value)
        existing = await self.repo.get(user_id, data.key)
        if existing is None:
            existing = Credential(user_id=user_id, key=data.key, encrypted_value=ciphertext)
            self.repo.add(existing)
        else:
            existing.encrypted_value = ciphertext
        await self.session.commit()
        await self.session.refresh(existing)
        return CredentialRead(
            key=existing.key, masked_value=mask_secret(data.value), updated_at=existing.updated_at
        )

    async def list(self, user_id: int) -> list[CredentialRead]:
        creds = await self.repo.list_for_user(user_id)
        out: list[CredentialRead] = []
        for c in creds:
            try:
                masked = mask_secret(decrypt_secret(c.encrypted_value))
            except SecretDecryptionError:
                masked = "****"  # stored under a different/rotated key
            out.append(CredentialRead(key=c.key, masked_value=masked, updated_at=c.updated_at))
        return out

    async def delete(self, user_id: int, key: CredentialKey) -> None:
        removed = await self.repo.delete(user_id, key)
        if not removed:
            raise CredentialNotFoundError()
        await self.session.commit()

    async def get_secret(self, user_id: int, key: CredentialKey) -> str | None:
        """Decrypted secret for internal use (provider calls). None if unset."""
        cred = await self.repo.get(user_id, key)
        if cred is None:
            return None
        try:
            return decrypt_secret(cred.encrypted_value)
        except SecretDecryptionError as exc:
            raise SecretUnreadableError() from exc
