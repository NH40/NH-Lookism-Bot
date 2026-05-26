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
        """Возвращает % сокращения КД от мастерства скорости.

        Использует переданную сессию (не создаёт новую), чтобы избежать
        лишних соединений с БД при каждом вызове.
        """
        from sqlalchemy import select
        from app.models.skill import UserMastery
        speed_levels = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
        try:
            r = await session.execute(
                select(UserMastery.speed).where(UserMastery.user_id == user_id)
            )
            speed = r.scalar_one_or_none()
            if speed is not None:
                return speed_levels.get(speed, 0)
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

    @staticmethod
    def pull_lock_key(user_id: int) -> str:
        return f"lock:pull:{user_id}"

    @staticmethod
    def recruit_lock_key(user_id: int) -> str:
        return f"lock:recruit:{user_id}"

    @staticmethod
    def buy_recruit_lock_key(user_id: int) -> str:
        return f"lock:buy_recruit:{user_id}"

    @staticmethod
    def train_lock_key(user_id: int, trainer_id: str) -> str:
        return f"lock:train:{trainer_id}:{user_id}"

    @staticmethod
    def biz_build_lock_key(user_id: int) -> str:
        return f"lock:biz_build:{user_id}"

    @staticmethod
    def promo_lock_key(user_id: int) -> str:
        return f"lock:promo:{user_id}"

    @staticmethod
    def treasury_lock_key(user_id: int) -> str:
        return f"lock:treasury:{user_id}"

    @staticmethod
    def duel_bot_key(user_id: int) -> str:
        return f"cd:duel_bot:{user_id}"

    @staticmethod
    def duel_lock_key(user_id: int) -> str:
        return f"lock:duel:{user_id}"

    @staticmethod
    def duel_challenge_key(to_user_id: int) -> str:
        return f"duel:challenge:{to_user_id}"

    @staticmethod
    def raid_lock_key(user_id: int) -> str:
        return f"lock:raid:{user_id}"

    @staticmethod
    def auction_bid_lock_key(user_id: int) -> str:
        return f"lock:auction_bid:{user_id}"

    @staticmethod
    def credit_lock_key(user_id: int) -> str:
        return f"lock:credit:{user_id}"

    @staticmethod
    def invest_lock_key(user_id: int) -> str:
        return f"lock:invest:{user_id}"

    @staticmethod
    def invest_withdraw_lock_key(invest_id: int) -> str:
        return f"lock:invest_wd:{invest_id}"

    @staticmethod
    def campaign_launch_lock_key(user_id: int) -> str:
        return f"lock:campaign_launch:{user_id}"

    @staticmethod
    def campaign_collect_lock_key(campaign_id: int) -> str:
        return f"lock:campaign_collect:{campaign_id}"

    # ── Новые локи (защита от race condition) ──────────────────────────────

    @staticmethod
    def casino_lock_key(user_id: int) -> str:
        return f"lock:casino:{user_id}"

    @staticmethod
    def card_action_lock_key(user_id: int) -> str:
        """Для discard, fusion, craft — одна операция с картой за раз."""
        return f"lock:card_action:{user_id}"

    @staticmethod
    def potion_buy_lock_key(user_id: int) -> str:
        return f"lock:potion_buy:{user_id}"

    @staticmethod
    def credit_repay_lock_key(user_id: int) -> str:
        return f"lock:credit_repay:{user_id}"

    async def acquire_lock(self, key: str, ttl: int = 5) -> bool:
        """Returns True if lock acquired, False if already locked.
        Uses atomic SET NX EX — single round-trip, no race window."""
        result = await self.redis.set(key, "1", nx=True, ex=ttl)
        return result is not None

    def format_ttl(self, seconds: int) -> str:
        if seconds <= 0:
            return "готово"
        m, s = divmod(seconds, 60)
        if m:
            return f"{m}м {s}с"
        return f"{s}с"


cooldown_service = CooldownService()