import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.cooldown_service import cooldown_service

TOM_LEE_COST = 3_000_000
TOM_LEE_CD_SECONDS = 7200
TOM_LEE_POINTS_MIN = 1
TOM_LEE_POINTS_MAX = 3

JEON_GON_COST = 1_000_000
JEON_GON_CD_SECONDS = 7200
JEON_GON_POINTS_MIN = 2
JEON_GON_POINTS_MAX = 5

TRAINERS = [
    {
        "id": "tom_lee",
        "name": "Том Ли",
        "emoji": "🥋",
        "description": "Мастер боевых искусств — очки мастерства",
        "cost": TOM_LEE_COST,
        "cd": TOM_LEE_CD_SECONDS,
        "reward": f"{TOM_LEE_POINTS_MIN}-{TOM_LEE_POINTS_MAX} очков мастерства",
    },
    {
        "id": "jeon_gon",
        "name": "Чон Гон",
        "emoji": "🧘",
        "description": "Наставник пути — очки пути",
        "cost": JEON_GON_COST,
        "cd": JEON_GON_CD_SECONDS,
        "reward": f"{JEON_GON_POINTS_MIN}-{JEON_GON_POINTS_MAX} очков пути",
    },
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

        if user.nh_coins < TOM_LEE_COST:
            return {
                "ok": False,
                "reason": f"Недостаточно NHCoin (нужно {TOM_LEE_COST:,})",
            }

        user.nh_coins -= TOM_LEE_COST
        user.coins_spent += TOM_LEE_COST

        points = random.randint(TOM_LEE_POINTS_MIN, TOM_LEE_POINTS_MAX)
        user.mastery_points += points

        await cooldown_service.set_cooldown(cd_key, TOM_LEE_CD_SECONDS)
        await session.flush()

        return {
            "ok": True,
            "points": points,
            "total_points": user.mastery_points,
            "cost": TOM_LEE_COST,
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

        if user.nh_coins < JEON_GON_COST:
            return {
                "ok": False,
                "reason": f"Недостаточно NHCoin (нужно {JEON_GON_COST:,})",
            }

        if not user.skill_path:
            return {
                "ok": False,
                "reason": "Сначала выбери путь в разделе Навыки",
            }

        user.nh_coins -= JEON_GON_COST
        user.coins_spent += JEON_GON_COST

        points = random.randint(JEON_GON_POINTS_MIN, JEON_GON_POINTS_MAX)
        user.skill_path_points += points

        await cooldown_service.set_cooldown(cd_key, JEON_GON_CD_SECONDS)
        await session.flush()

        return {
            "ok": True,
            "points": points,
            "total_points": user.skill_path_points,
            "cost": JEON_GON_COST,
            "type": "path",
        }


training_service = TrainingService()