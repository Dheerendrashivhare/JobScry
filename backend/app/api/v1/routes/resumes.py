"""Resume routes, nested under a profile (multipart upload + metadata)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, DBSession, PageParams
from app.schemas.common import Page
from app.schemas.resume import ResumeRead, ResumeUpdate
from app.services.resume import ResumeService

router = APIRouter(prefix="/profiles/{profile_id}/resumes", tags=["resumes"])


@router.post("", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    profile_id: int,
    current_user: CurrentUser,
    session: DBSession,
    file: Annotated[UploadFile, File()],
) -> ResumeRead:
    content = await file.read()
    return await ResumeService(session).create(
        current_user.id, profile_id, file.filename or "resume", content
    )


@router.get("", response_model=Page[ResumeRead])
async def list_resumes(
    profile_id: int, current_user: CurrentUser, session: DBSession, page: PageParams
) -> Page[ResumeRead]:
    return await ResumeService(session).list(current_user.id, profile_id, page)


@router.get("/{resume_id}", response_model=ResumeRead)
async def get_resume(
    profile_id: int, resume_id: int, current_user: CurrentUser, session: DBSession
) -> ResumeRead:
    return await ResumeService(session).get(current_user.id, profile_id, resume_id)


@router.get("/{resume_id}/download")
async def download_resume(
    profile_id: int, resume_id: int, current_user: CurrentUser, session: DBSession
) -> FileResponse:
    path, filename = await ResumeService(session).storage_path_for(
        current_user.id, profile_id, resume_id
    )
    return FileResponse(path, filename=filename)


@router.patch("/{resume_id}", response_model=ResumeRead)
async def update_resume(
    profile_id: int,
    resume_id: int,
    data: ResumeUpdate,
    current_user: CurrentUser,
    session: DBSession,
) -> ResumeRead:
    # Only meaningful action today is promoting to primary.
    if data.is_primary:
        return await ResumeService(session).set_primary(current_user.id, profile_id, resume_id)
    return await ResumeService(session).get(current_user.id, profile_id, resume_id)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_resume(
    profile_id: int, resume_id: int, current_user: CurrentUser, session: DBSession
) -> None:
    await ResumeService(session).delete(current_user.id, profile_id, resume_id)
