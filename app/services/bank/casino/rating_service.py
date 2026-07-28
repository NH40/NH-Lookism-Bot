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

    async def get_user_rank(self, session: AsyncSession, user_id: int) -> tuple[int, int]:
        """Место пользователя в общем недельном рейтинге (независимо от знака
        результата) и сам результат."""
        from sqlalchemy import func
        user_value = await session.scalar(
            select(User.casino_weekly_coins_won).where(User.id == user_id)
        ) or 0
        ahead = await session.scalar(
            select(func.count()).select_from(User).where(User.casino_weekly_coins_won > user_value)
        ) or 0
        return ahead + 1, user_value

    async def reset_and_reward(self, session: AsyncSession) -> list[dict]:
        """Награждает топ-3, обнуляет счётчик у всех. Возвращает данные для уведомлений.

        Топ-3 также получают игровые титулы (Джекпот/Блэкджек/Игрок) — держатель
        меняется каждую неделю, у прошлого держателя титул снимается.
        """
        top3 = await self.get_top(session, limit=3)

        # Снимаем титулы со всех прежних держателей — каждую неделю ровно 1 обладатель на титул
        await session.execute(update(User).values(
            title_casino_jackpot=False,
            title_casino_blackjack=False,
            title_casino_player=False,
        ))

        title_fields = {1: "title_casino_jackpot", 2: "title_casino_blackjack", 3: "title_casino_player"}

        rewarded: list[dict] = []
        for rank, user in enumerate(top3, start=1):
            reward = CASINO_RATING_REWARDS.get(rank)
            if not reward:
                continue
            user.nh_coins = (user.nh_coins or 0) + reward.get("nh_coins", 0)
            user.tickets = (user.tickets or 0) + reward.get("tickets", 0)
            field = title_fields.get(rank)
            if field:
                setattr(user, field, True)
            rewarded.append({
                "tg_id": user.tg_id,
                "rank": rank,
                "net_won": user.casino_weekly_coins_won,
                "reward": reward,
            })

        await session.execute(update(User).values(casino_weekly_coins_won=0))
        return rewarded


casino_rating_service = CasinoRatingService()
