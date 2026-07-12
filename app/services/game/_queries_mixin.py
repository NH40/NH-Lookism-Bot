"""CityQueriesMixin — read-only запросы к городам, районам, КД атак."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.user import User
from app.models.city import City, District
from app.services.cooldown_service import cooldown_service

ATTACK_CD: dict[str, int] = {
    "gang":    60,
    "king":    300,
    "fist":    600,
    "emperor": 1000,
}


class CityQueriesMixin:

    def _get_district_power(self, district_number: int, multiplier: float) -> int:
        return max(10, int(10 * (district_number ** 0.6) * multiplier))

    async def _get_my_districts_in_city(
        self, session: AsyncSession, user_id: int, city_id: int
    ) -> int:
        r = await session.scalar(
            select(func.count(District.id)).where(
                District.owner_id == user_id,
                District.city_id == city_id,
                District.is_captured == True,
            )
        )
        return r or 0

    async def _count_my_king_cities(
        self, session: AsyncSession, user_id: int
    ) -> int:
        r = await session.execute(
            select(District.city_id)
            .join(City, City.id == District.city_id)
            .where(
                District.owner_id == user_id,
                District.is_captured == True,
                City.phase != "fist",
            ).distinct()
        )
        return len(r.scalars().all())

    async def _get_city_dominant_player(
        self, session: AsyncSession, city_id: int, exclude_user_id: int
    ) -> int | None:
        from sqlalchemy import desc
        r = await session.execute(
            select(District.owner_id, func.count(District.id).label("cnt"))
            .where(
                District.city_id == city_id,
                District.is_captured == True,
                District.owner_id != None,
                District.owner_id != exclude_user_id,
            )
            .group_by(District.owner_id)
            .order_by(desc("cnt"))
            .limit(1)
        )
        row = r.first()
        return row[0] if row else None

    async def _get_max_extra_attacks_async(
        self, session: AsyncSession, user: User
    ) -> int:
        if not user.double_attack:
            return 0
        from app.models.skill import UserPathSkills
        from app.data.skills import PATH_SKILLS
        all_skills = {s.skill_id: s for skills in PATH_SKILLS.values() for s in skills}
        extra_atk_ids = [sid for sid, s in all_skills.items() if "extra_attack_count" in s.effect]
        owned_r = await session.execute(
            select(UserPathSkills.skill_id).where(
                UserPathSkills.user_id == user.id,
                UserPathSkills.skill_id.in_(extra_atk_ids),
            )
        )
        count = sum(all_skills[sid].effect["extra_attack_count"] for sid in owned_r.scalars().all())
        from app.repositories.title_repo import title_repo
        if await title_repo.has_set(session, user.id, "monster"):
            count += 1
        return max(count, 1)

    async def _handle_attack_cd(
        self, session: AsyncSession, user: User, cd_key: str, phase: str
    ) -> None:
        if user.extra_attack_count > 0:
            user.extra_attack_count -= 1
            return
        base_cd = ATTACK_CD[phase]
        from app.models.skill import UserMastery
        mr = await session.execute(
            select(UserMastery).where(UserMastery.user_id == user.id)
        )
        mastery = mr.scalar_one_or_none()
        speed_pct = 0
        if mastery:
            speed_level = min(4, mastery.speed + getattr(user, "clan_land_speed_mastery_bonus", 0))
            raw = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}.get(speed_level, 0)
            speed_pct = int(raw * user.skill_path_bonus_multiplier)
        from app.repositories.title_repo import title_repo
        title_ids = set(await title_repo.get_user_titles(session, user.id))
        flow_titles = {"concentration", "focus"}
        if flow_titles.issubset(title_ids):
            speed_pct = min(80, speed_pct + 15)
        if "reverse_eyes" in title_ids:
            speed_pct = min(80, speed_pct + 30)
        if "concentration" in title_ids:
            speed_pct = min(80, speed_pct + 30)
        cd = max(10, int(base_cd * (1 - speed_pct / 100)))
        await cooldown_service.set_cooldown(cd_key, cd)
        user.extra_attack_count = await self._get_max_extra_attacks_async(session, user)
