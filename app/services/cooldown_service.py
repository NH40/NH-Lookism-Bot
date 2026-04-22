import redis.asyncio as aioredis
from app.config import settings


class CooldownService:
    def __init__(self):
        self.redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    async def set_cooldown(self, key: str, seconds: int) -> None:
        await self.redis.setex(key, seconds, "1")

    async def get_ttl(self, key: str) -> int:
        """Возвращает секунды до конца КД. 0 = КД нет."""
        ttl = await self.redis.ttl(key)
        return max(0, ttl)

    async def is_on_cooldown(self, key: str) -> bool:
        return await self.redis.exists(key) == 1

    async def clear_cooldown(self, key: str) -> None:
        await self.redis.delete(key)
    
    async def get_speed_reduction(self, session, user_id: int) -> int:
        """Возвращает % сокращения КД от мастерства скорости."""
        from sqlalchemy import select
        from app.models.skill import UserMastery
        from app.database import AsyncSessionFactory
        speed_levels = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
        try:
            async with AsyncSessionFactory() as session:
                r = await session.execute(
                    select(UserMastery).where(UserMastery.user_id == user_id)
                )
                mastery = r.scalar_one_or_none()
                if mastery:
                    return speed_levels.get(mastery.speed, 0)
        except Exception:
            pass
        return 0

    def apply_speed_reduction(self, base_cd: int, speed_pct: int, extra_pct: int = 0) -> int:
        """Применяет сокращение КД от скорости + доп. бонусов."""
        total = speed_pct + extra_pct
        return max(10, int(base_cd * (1 - total / 100)))

    # ── Ключи ───────────────────────────────────────────────────────────────
    @staticmethod
    def attack_key(user_id: int) -> str:
        return f"cd:attack:{user_id}"

    @staticmethod
    def recruit_key(user_id: int) -> str:
        return f"cd:recruit:{user_id}"

    @staticmethod
    def train_key(user_id: int) -> str:
        return f"cd:train:{user_id}"

    @staticmethod
    def ticket_key(user_id: int) -> str:
        return f"cd:ticket:{user_id}"

    @staticmethod
    def double_train_key(user_id: int) -> str:
        return f"cd:dtrain:{user_id}"

    def format_ttl(self, seconds: int) -> str:
        if seconds <= 0:
            return "готово"
        m, s = divmod(seconds, 60)
        if m:
            return f"{m}м {s}с"
        return f"{s}с"


cooldown_service = CooldownService()