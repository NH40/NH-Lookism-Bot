import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.skill import UserMastery
from app.services.cooldown_service import cooldown_service

TOM_LEE_COST = 3_000_000        # 3 млн NHCoin
TOM_LEE_CD_SECONDS = 7200       # 2 часа
TOM_LEE_POINTS_MIN = 1
TOM_LEE_POINTS_MAX = 3

TRAINERS = [
    {
        "id": "tom_lee",
        "name": "Том Ли",
        "emoji": "🥋",
        "description": "Легендарный мастер боевых искусств",
        "cost": TOM_LEE_COST,
        "cd": TOM_LEE_CD_SECONDS,
        "reward": f"{TOM_LEE_POINTS_MIN}-{TOM_LEE_POINTS_MAX} очков мастерства",
    }
]


class TrainingService:

    def trainer_cd_key(self, user_id: int, trainer_id: str) -> str:
        return f"trainer:{trainer_id}:{user_id}"

    async def get_trainers_info(self, user_id: int) -> list[dict]:
        result = []
        for t in TRAINERS:
            cd_key = self.trainer_cd_key(user_id, t["id"])
            on_cd = await cooldown_service.is_on_cooldown(cd_key)
            ttl = await cooldown_service.get_ttl(cd_key) if on_cd else 0
            result.append({
                **t,
                "on_cd": on_cd,
                "ttl": ttl,
            })
        return result

    async def train_with_tom(
        self, session: AsyncSession, user: User
    ) -> dict:
        cd_key = self.trainer_cd_key(user.id, "tom_lee")

        # Проверяем КД
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {
                "ok": False,
                "reason": f"Том Ли отдыхает: {cooldown_service.format_ttl(ttl)}",
                "cd": ttl,
            }

        # Проверяем монеты
        if user.nh_coins < TOM_LEE_COST:
            return {
                "ok": False,
                "reason": f"Недостаточно NHCoin (нужно {TOM_LEE_COST:,})",
            }

        # Списываем монеты
        user.nh_coins -= TOM_LEE_COST
        user.coins_spent += TOM_LEE_COST

        # Выдаём случайные очки мастерства
        points = random.randint(TOM_LEE_POINTS_MIN, TOM_LEE_POINTS_MAX)
        user.mastery_points += points

        # Устанавливаем КД
        await cooldown_service.set_cooldown(cd_key, TOM_LEE_CD_SECONDS)

        await session.flush()

        return {
            "ok": True,
            "points": points,
            "total_points": user.mastery_points,
            "cost": TOM_LEE_COST,
        }


training_service = TrainingService()