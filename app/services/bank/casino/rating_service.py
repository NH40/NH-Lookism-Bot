"""Еженедельный рейтинг казино (по чистой прибыли в NHCoin)."""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.constants.bank import CASINO_RATING_REWARDS


class CasinoRatingService:

    async def get_top(self, session: AsyncSession, limit: int = 10) -> list[User]:
        result = await session.execute(
            select(User)
            .where(User.casino_weekly_coins_won > 0)
            .order_by(User.casino_weekly_coins_won.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def reset_and_reward(self, session: AsyncSession) -> list[dict]:
        """Награждает топ-3, обнуляет счётчик у всех. Возвращает данные для уведомлений."""
        top3 = await self.get_top(session, limit=3)

        rewarded: list[dict] = []
        for rank, user in enumerate(top3, start=1):
            reward = CASINO_RATING_REWARDS.get(rank)
            if not reward:
                continue
            user.nh_coins = (user.nh_coins or 0) + reward.get("nh_coins", 0)
            user.tickets = (user.tickets or 0) + reward.get("tickets", 0)
            rewarded.append({
                "tg_id": user.tg_id,
                "rank": rank,
                "net_won": user.casino_weekly_coins_won,
                "reward": reward,
            })

        await session.execute(update(User).values(casino_weekly_coins_won=0))
        return rewarded


casino_rating_service = CasinoRatingService()
