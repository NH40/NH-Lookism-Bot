"""SkillService — основной класс, делегирует к mastery.py и path.py."""
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.skill import UserMastery, UserPathSkills
from app.data.skills import MASTERY_BY_ID, PATH_SKILLS, PATH_SYNERGIES
from app.constants.raid import (
    PATH_LEVEL_COSTS, PATH_LEVEL_MAX, PATH_LEVEL_BONUSES, PATH_AWAKENING_BONUSES,
)


def _all_path_skills_map() -> dict:
    result = {}
    for path_skills in PATH_SKILLS.values():
        for s in path_skills:
            result[s.skill_id] = s
    return result


class SkillService:

    # ── Мастерство ───────────────────────────────────────────────────────────

    async def get_or_create_mastery(
        self, session: AsyncSession, user_id: int
    ) -> UserMastery:
        from app.services.skill.mastery import get_or_create_mastery
        return await get_or_create_mastery(session, user_id)

    async def upgrade_mastery(
        self, session: AsyncSession, user: User, skill_id: str
    ) -> dict:
        from app.services.skill.mastery import upgrade_mastery
        return await upgrade_mastery(session, user, skill_id)

    async def _apply_mastery_bonus(
        self, session: AsyncSession, user: User, skill_id: str, level: int
    ) -> None:
        from app.services.skill.mastery import _apply_mastery_bonus
        await _apply_mastery_bonus(session, user, skill_id, level)

    # ── Путь навыков ─────────────────────────────────────────────────────────

    async def choose_path(
        self, session: AsyncSession, user: User, path: str
    ) -> dict:
        from app.services.skill.path import choose_path
        return await choose_path(session, user, path)

    async def upgrade_path_level(self, session: AsyncSession, user: User) -> dict:
        from app.services.skill.path import upgrade_path_level
        return await upgrade_path_level(session, user)

    async def _apply_synergy(
        self, session: AsyncSession, user: User, foreign_path: str
    ) -> dict | None:
        from app.services.skill.path import apply_synergy
        return await apply_synergy(session, user, foreign_path)

    async def _check_and_awaken(self, session: AsyncSession, user: User) -> bool:
        from app.services.skill.path import check_and_awaken
        return await check_and_awaken(session, user)

    async def buy_path_skill(
        self, session: AsyncSession, user: User, skill_id: str
    ) -> dict:
        from app.services.skill.path import buy_path_skill
        return await buy_path_skill(session, user, skill_id)

    async def _apply_path_skill(self, session, user: User, skill) -> None:
        from app.services.skill.path import apply_path_skill
        await apply_path_skill(session, user, skill)

    def _update_extra_attack(self, user: User) -> None:
        from app.services.skill.path import update_extra_attack
        update_extra_attack(user)

    async def get_path_skills_bought(
        self, session: AsyncSession, user_id: int
    ) -> list[str]:
        from app.services.skill.path import get_path_skills_bought
        return await get_path_skills_bought(session, user_id)

    async def get_extra_path_skills_count(
        self, session: AsyncSession, user: User
    ) -> int:
        from app.services.skill.path import get_extra_path_skills_count
        return await get_extra_path_skills_count(session, user)

    async def spin_for_random_extra_skill(
        self, session: AsyncSession, user: User
    ) -> dict:
        from app.services.skill.path import spin_for_random_extra_skill
        return await spin_for_random_extra_skill(session, user)

    async def buy_extra_path_skill(
        self, session: AsyncSession, user: User, skill_id: str
    ) -> dict:
        from app.services.skill.path import buy_extra_path_skill
        return await buy_extra_path_skill(session, user, skill_id)


skill_service = SkillService()
