from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from app.models.user import User
from app.models.squad_member import SquadMember
from app.models.building import UserBuilding
from app.models.character import UserCharacter
from app.models.city import District
from app.models.skill import UserMastery, UserPathSkills


MAX_PRESTIGE = 10


class PrestigeService:

    def can_prestige(self, user: User) -> tuple[bool, str]:
        if user.phase != "emperor":
            return False, "Пробуждение доступно только Императорам"
        if user.prestige_level >= MAX_PRESTIGE:
            return False, f"Достигнут максимальный уровень ({MAX_PRESTIGE})"
        return True, ""

    async def do_prestige(self, session: AsyncSession, user: User) -> dict:
        ok, reason = self.can_prestige(user)
        if not ok:
            return {"ok": False, "reason": reason}

        user.prestige_level += 1
        user.prestige_income_bonus += 5
        user.prestige_recruit_bonus += 5
        user.prestige_train_bonus += 5
        user.prestige_ticket_bonus += 1
        user.ticket_chance = min(95, user.ticket_chance + 1)

        await self._reset_progress(session, user)
        return {"ok": True, "level": user.prestige_level}

    async def _reset_progress(self, session: AsyncSession, user: User) -> None:
        """Сброс прогресса кроме донатов и пробуждений."""
        user.phase = "gang"
        user.sector = None
        user.gang_city_id = None
        user.king_cities_count = 0
        user.fist_wins = 0
        user.fist_cities_count = 0
        user.nh_coins = 0
        user.influence = 100
        user.combat_power = 0
        user.business_path = None
        user.income_per_minute = 0
        user.income_bonus_percent = 0
        user.building_discount_percent = 0
        user.district_multiplier = 1.0
        user.tickets = 0
        user.max_tickets = 3
        user.ticket_chance = 25
        user.recruit_count_bonus = 0
        user.double_recruit = False
        user.train_bonus_percent = 0
        user.train_quality_bonus = 0
        user.double_train = False
        user.double_attack = False
        user.double_attack_used = False
        user.extra_attack_count = 0
        user.skill_path = None
        user.skill_path_points = 0
        user.skill_path_bonus_multiplier = 1.0

        # Чистим таблицы
        await session.execute(
            delete(SquadMember).where(SquadMember.user_id == user.id)
        )
        await session.execute(
            delete(UserBuilding).where(UserBuilding.user_id == user.id)
        )
        await session.execute(
            delete(UserCharacter).where(UserCharacter.user_id == user.id)
        )
        await session.execute(
            delete(District).where(District.owner_id == user.id)
        )
        await session.execute(
            delete(UserPathSkills).where(UserPathSkills.user_id == user.id)
        )

        # Сбрасываем мастерство
        from sqlalchemy import select
        r = await session.execute(
            select(UserMastery).where(UserMastery.user_id == user.id)
        )
        mastery = r.scalar_one_or_none()
        if mastery:
            mastery.strength = 0
            mastery.speed = 0
            mastery.endurance = 0
            mastery.technique = 0

        # Переприменяем донат-бонусы
        from app.services.title_service import title_service
        await title_service.reapply_all_titles(session, user)

        await session.flush()


prestige_service = PrestigeService()