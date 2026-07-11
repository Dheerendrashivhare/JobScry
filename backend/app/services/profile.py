"""Profile use-cases: CRUD plus per-profile skill management.

Enforces one default profile per user and keeps the canonical skill vocabulary in
sync via :class:`SkillRepository`. All reads are scoped to the owning user.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ProfileNotFoundError, ResourceNotFoundError
from app.models import DEFAULT_SCORING_WEIGHTS, Profile, ProfileSkill
from app.repositories.profile import ProfileRepository
from app.repositories.skill import SkillRepository
from app.schemas.common import Page, Pagination
from app.schemas.profile import (
    ProfileCreate,
    ProfileRead,
    ProfileSkillCreate,
    ProfileSkillRead,
    ProfileUpdate,
)


def _to_read(profile: Profile) -> ProfileRead:
    return ProfileRead(
        id=profile.id,
        name=profile.name,
        headline=profile.headline,
        is_default=profile.is_default,
        experience_min_years=profile.experience_min_years,
        experience_max_years=profile.experience_max_years,
        target_roles=profile.target_roles,
        preferred_companies=profile.preferred_companies,
        ignored_companies=profile.ignored_companies,
        certifications=profile.certifications,
        languages=profile.languages,
        locations=profile.locations,
        work_modes=profile.work_modes,
        scoring_weights=profile.scoring_weights,
        min_score=profile.min_score,
        company_size_mode=profile.company_size_mode,
        max_headcount=profile.max_headcount,
        skills=[
            ProfileSkillRead(
                id=ps.id,
                name=ps.skill.name,
                weight=ps.weight,
                is_required=ps.is_required,
                proficiency=ps.proficiency,
            )
            for ps in profile.profile_skills
        ],
        created_at=profile.created_at,
    )


class ProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProfileRepository(session)
        self.skills = SkillRepository(session)

    async def _require(self, user_id: int, profile_id: int) -> Profile:
        profile = await self.repo.get_for_user(profile_id, user_id)
        if profile is None:
            raise ProfileNotFoundError()
        return profile

    async def create(self, user_id: int, data: ProfileCreate) -> ProfileRead:
        profile = Profile(
            user_id=user_id,
            name=data.name,
            headline=data.headline,
            experience_min_years=data.experience_min_years,
            experience_max_years=data.experience_max_years,
            target_roles=data.target_roles,
            preferred_companies=data.preferred_companies,
            ignored_companies=data.ignored_companies,
            certifications=data.certifications,
            languages=data.languages,
            locations=data.locations,
            work_modes=data.work_modes,
            scoring_weights=data.scoring_weights or dict(DEFAULT_SCORING_WEIGHTS),
            min_score=data.min_score,
            company_size_mode=data.company_size_mode,
            max_headcount=data.max_headcount,
        )
        # First profile (or an explicit request) becomes the default; only one per user.
        if data.is_default or await self.repo.count_for_user(user_id) == 0:
            await self.repo.clear_default(user_id)
            profile.is_default = True

        self.repo.add(profile)
        await self.session.flush()  # assign profile.id

        # Insert skills by FK (never touch the lazy collection) — see add_skill.
        for entry in data.skills:
            skill = await self.skills.get_or_create(entry.name)
            self.session.add(
                ProfileSkill(
                    profile_id=profile.id,
                    skill_id=skill.id,
                    weight=entry.weight,
                    is_required=entry.is_required,
                    proficiency=entry.proficiency,
                )
            )
        await self.session.commit()
        return await self.get(user_id, profile.id)

    async def get(self, user_id: int, profile_id: int) -> ProfileRead:
        return _to_read(await self._require(user_id, profile_id))

    async def list(self, user_id: int, page: Pagination) -> Page[ProfileRead]:
        items = await self.repo.list_for_user(user_id, page.limit, page.offset)
        total = await self.repo.count_for_user(user_id)
        return Page(
            items=[_to_read(p) for p in items],
            total=total,
            limit=page.limit,
            offset=page.offset,
        )

    async def update(self, user_id: int, profile_id: int, data: ProfileUpdate) -> ProfileRead:
        profile = await self._require(user_id, profile_id)
        payload = data.model_dump(exclude_unset=True)
        make_default = payload.pop("is_default", None)
        for field, value in payload.items():
            setattr(profile, field, value)
        if make_default is True:
            await self.repo.clear_default(user_id)
            profile.is_default = True
        await self.session.commit()
        return await self.get(user_id, profile_id)

    async def delete(self, user_id: int, profile_id: int) -> None:
        profile = await self._require(user_id, profile_id)
        await self.repo.delete(profile)
        await self.session.commit()

    async def add_skill(
        self, user_id: int, profile_id: int, data: ProfileSkillCreate
    ) -> ProfileRead:
        profile = await self._require(user_id, profile_id)
        skill = await self.skills.get_or_create(data.name)
        if any(ps.skill_id == skill.id for ps in profile.profile_skills):
            raise ConflictError("Skill already on profile")
        self.session.add(
            ProfileSkill(
                profile_id=profile.id,
                skill_id=skill.id,
                weight=data.weight,
                is_required=data.is_required,
                proficiency=data.proficiency,
            )
        )
        await self.session.commit()
        return await self.get(user_id, profile_id)

    async def remove_skill(self, user_id: int, profile_id: int, profile_skill_id: int) -> None:
        profile = await self._require(user_id, profile_id)
        target = next((ps for ps in profile.profile_skills if ps.id == profile_skill_id), None)
        if target is None:
            raise ResourceNotFoundError("Skill not on profile")
        await self.session.delete(target)
        await self.session.commit()
