import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.cooldown_service import cooldown_service
from app.models.skill import UserMastery
from sqlalchemy import select

from app.constants.training import (
    TOM_LEE_COST, TOM_LEE_CD_SECONDS, TOM_LEE_POINTS_MIN, TOM_LEE_POINTS_MAX,
    JEON_GON_COST, JEON_GON_CD_SECONDS, JEON_GON_POINTS_MIN, JEON_GON_POINTS_MAX,
    MANAGER_KIM_COST, MANAGER_KIM_CD_SECONDS, MANAGER_KIM_POINTS_MIN, MANAGER_KIM_POINTS_MAX,
    TRAINERS,
)

class TrainingService:

    def trainer_cd_key(self, user_id: int, trainer_id: str) -> str:
        return f"trainer:{trainer_id}:{user_id}"

    async def get_trainers_info(self, user_id: int) -> list[dict]:
        result = []
        for t in TRAINERS:
            cd_key = self.trainer_cd_key(user_id, t["id"])
            on_cd = await cooldown_service.is_on_cooldown(cd_key)
            ttl = await cooldown_service.get_ttl(cd_key) if on_cd else 0
            result.append({**t, "on_cd": on_cd, "ttl": ttl})
        return result

    async def train_with_tom(self, session: AsyncSession, user: User) -> dict:
        cd_key = self.trainer_cd_key(user.id, "tom_lee")

        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {
                "ok": False,
                "reason": f"Том Ли отдыхает: {cooldown_service.format_ttl(ttl)}",
                "cd": ttl,
            }

        discount = getattr(user, 'circ_trainer_discount', 0)
        effective_cost = max(1, int(TOM_LEE_COST * (1 - discount / 100)))
        if user.nh_coins < effective_cost:
            return {
                "ok": False,
                "reason": f"Недостаточно NHCoin (нужно {effective_cost:,})",
            }

        user.nh_coins -= effective_cost
        user.coins_spent += effective_cost

        points = random.randint(TOM_LEE_POINTS_MIN, TOM_LEE_POINTS_MAX)
        points = int(points * (1 + getattr(user, 'clan_land_mastery_pct', 0) / 100))
        user.mastery_points += points

        speed = await session.scalar(select(UserMastery.speed).where(UserMastery.user_id == user.id))
        speed_level = 4 if getattr(user, 'fame_charles_invisible', False) else min(
            4, (speed or 0) + getattr(user, 'clan_land_speed_mastery_bonus', 0)
        )
        raw_speed = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}.get(speed_level, 0)
        extra = (getattr(user, 'trainer_cd_reduction', 0) + getattr(user, 'ticket_cd_reduction', 0))
        cd = cooldown_service.apply_speed_reduction(TOM_LEE_CD_SECONDS, raw_speed, extra_pct=extra)
        await cooldown_service.set_cooldown(cd_key, cd)

        await session.flush()

        return {
            "ok": True,
            "points": points,
            "total_points": user.mastery_points,
            "cost": effective_cost,
            "type": "mastery",
        }

    async def train_with_jeon_gon(self, session: AsyncSession, user: User) -> dict:
        cd_key = self.trainer_cd_key(user.id, "jeon_gon")

        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {
                "ok": False,
                "reason": f"Чон Гон медитирует: {cooldown_service.format_ttl(ttl)}",
                "cd": ttl,
            }

        discount = getattr(user, 'circ_trainer_discount', 0)
        effective_cost = max(1, int(JEON_GON_COST * (1 - discount / 100)))
        if user.nh_coins < effective_cost:
            return {
                "ok": False,
                "reason": f"Недостаточно NHCoin (нужно {effective_cost:,})",
            }

        if not user.skill_path:
            return {
                "ok": False,
                "reason": "Сначала выбери путь в разделе Навыки",
            }

        user.nh_coins -= effective_cost
        user.coins_spent += effective_cost

        points = random.randint(JEON_GON_POINTS_MIN, JEON_GON_POINTS_MAX)
        points = int(points * (1 + getattr(user, 'clan_land_mastery_pct', 0) / 100))
        user.skill_path_points += points

        speed = await session.scalar(select(UserMastery.speed).where(UserMastery.user_id == user.id))
        speed_level = 4 if getattr(user, 'fame_charles_invisible', False) else min(
            4, (speed or 0) + getattr(user, 'clan_land_speed_mastery_bonus', 0)
        )
        raw_speed = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}.get(speed_level, 0)
        extra = (getattr(user, 'trainer_cd_reduction', 0) + getattr(user, 'ticket_cd_reduction', 0))
        cd = cooldown_service.apply_speed_reduction(JEON_GON_CD_SECONDS, raw_speed, extra_pct=extra)
        await cooldown_service.set_cooldown(cd_key, cd)

        await session.flush()

        return {
            "ok": True,
            "points": points,
            "total_points": user.skill_path_points,
            "cost": effective_cost,
            "type": "path",
        }


    async def train_with_manager_kim(self, session: AsyncSession, user: User) -> dict:
        cd_key = self.trainer_cd_key(user.id, "manager_kim")

        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {
                "ok": False,
                "reason": f"Менеджер Ким занят: {cooldown_service.format_ttl(ttl)}",
                "cd": ttl,
            }

        if user.nh_coins < MANAGER_KIM_COST:
            return {
                "ok": False,
                "reason": f"Недостаточно NHCoin (нужно {MANAGER_KIM_COST:,})",
            }

        user.nh_coins -= MANAGER_KIM_COST
        user.coins_spent += MANAGER_KIM_COST

        points = random.randint(MANAGER_KIM_POINTS_MIN, MANAGER_KIM_POINTS_MAX)
        user.war_points = getattr(user, "war_points", 0) + points

        speed = await session.scalar(select(UserMastery.speed).where(UserMastery.user_id == user.id))
        speed_level = 4 if getattr(user, 'fame_charles_invisible', False) else min(
            4, (speed or 0) + getattr(user, 'clan_land_speed_mastery_bonus', 0)
        )
        raw_speed = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}.get(speed_level, 0)
        extra = (getattr(user, 'trainer_cd_reduction', 0) + getattr(user, 'ticket_cd_reduction', 0))
        cd = cooldown_service.apply_speed_reduction(MANAGER_KIM_CD_SECONDS, raw_speed, extra_pct=extra)
        await cooldown_service.set_cooldown(cd_key, cd)

        await session.flush()

        return {
            "ok": True,
            "points": points,
            "total_points": user.war_points,
            "cost": MANAGER_KIM_COST,
            "type": "war",
        }


training_service = TrainingService()