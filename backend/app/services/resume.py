"""Resume use-cases: validated multipart upload + metadata management.

Files are validated by extension (PDF/DOCX/LaTeX only, CLAUDE.md §11), stored on
disk under ``resume_storage_dir/<user_id>/`` with a random name, and recorded with
``parse_status = pending`` — actual text extraction lands in a later phase. The
first resume on a profile becomes primary automatically.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    ProfileNotFoundError,
    ResumeNotFoundError,
    ResumeTooLargeError,
    UnsupportedResumeFormatError,
)
from app.models import Resume
from app.models.enums import ResumeFormat, ResumeParseStatus
from app.repositories.profile import ProfileRepository
from app.repositories.resume import ResumeRepository
from app.schemas.common import Page, Pagination
from app.schemas.resume import ResumeRead

_EXTENSION_FORMATS: dict[str, ResumeFormat] = {
    ".pdf": ResumeFormat.PDF,
    ".docx": ResumeFormat.DOCX,
    ".tex": ResumeFormat.LATEX,
}


class ResumeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ResumeRepository(session)
        self.profiles = ProfileRepository(session)

    async def _require_profile(self, user_id: int, profile_id: int) -> None:
        if await self.profiles.get_for_user(profile_id, user_id) is None:
            raise ProfileNotFoundError()

    async def _require_resume(self, user_id: int, profile_id: int, resume_id: int) -> Resume:
        await self._require_profile(user_id, profile_id)
        resume = await self.repo.get(resume_id, profile_id)
        if resume is None:
            raise ResumeNotFoundError()
        return resume

    async def create(
        self, user_id: int, profile_id: int, filename: str, content: bytes
    ) -> ResumeRead:
        await self._require_profile(user_id, profile_id)
        settings = get_settings()

        fmt = _EXTENSION_FORMATS.get(Path(filename).suffix.lower())
        if fmt is None:
            raise UnsupportedResumeFormatError()
        if len(content) > settings.resume_max_bytes:
            raise ResumeTooLargeError()

        storage_dir = Path(settings.resume_storage_dir) / str(user_id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        stored_path = storage_dir / f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
        stored_path.write_bytes(content)

        resume = Resume(
            profile_id=profile_id,
            filename=filename,
            format=fmt,
            storage_path=str(stored_path),
            parse_status=ResumeParseStatus.PENDING,
        )
        if await self.repo.count_for_profile(profile_id) == 0:
            resume.is_primary = True
        self.repo.add(resume)
        await self.session.commit()
        await self.session.refresh(resume)
        return ResumeRead.model_validate(resume)

    async def list(self, user_id: int, profile_id: int, page: Pagination) -> Page[ResumeRead]:
        await self._require_profile(user_id, profile_id)
        items = await self.repo.list_for_profile(profile_id, page.limit, page.offset)
        total = await self.repo.count_for_profile(profile_id)
        return Page(
            items=[ResumeRead.model_validate(r) for r in items],
            total=total,
            limit=page.limit,
            offset=page.offset,
        )

    async def get(self, user_id: int, profile_id: int, resume_id: int) -> ResumeRead:
        return ResumeRead.model_validate(await self._require_resume(user_id, profile_id, resume_id))

    async def set_primary(self, user_id: int, profile_id: int, resume_id: int) -> ResumeRead:
        resume = await self._require_resume(user_id, profile_id, resume_id)
        await self.repo.clear_primary(profile_id)
        resume.is_primary = True
        await self.session.commit()
        await self.session.refresh(resume)
        return ResumeRead.model_validate(resume)

    async def delete(self, user_id: int, profile_id: int, resume_id: int) -> None:
        resume = await self._require_resume(user_id, profile_id, resume_id)
        Path(resume.storage_path).unlink(missing_ok=True)
        await self.repo.delete(resume)
        await self.session.commit()

    async def storage_path_for(
        self, user_id: int, profile_id: int, resume_id: int
    ) -> tuple[str, str]:
        """Return (path, download_filename) for a download response."""
        resume = await self._require_resume(user_id, profile_id, resume_id)
        return resume.storage_path, resume.filename
