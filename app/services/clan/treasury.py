import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.clan import Clan
from app.services.clan.base import ClanBaseService


class ClanTreasuryService(ClanBaseService):

    async def deposit_treasury(
        self, session: AsyncSession, clan: Clan, user: User, amount: int
    ) -> dict:
        if amount <= 0:
            return {"ok": False, "reason": "Сумма должна быть больше 0"}
        if user.nh_coins < amount:
            return {"ok": False, "reason": f"Недостаточно NHCoin (есть {user.nh_coins:,})"}

        user.nh_coins -= amount
        clan.treasury += amount
        await session.flush()

        # Круговой донат «Глава клана» круг 5: кешбэк 3% шанс вернуть 5-10% депозита
        cashback = 0
        cashback_pct = 0
        if getattr(user, "circ_clan_cashback", False) and random.randint(1, 100) <= 3:
            cashback_pct = random.randint(5, 10)
            cashback = int(amount * cashback_pct / 100)
            if cashback > 0:
                user.nh_coins += cashback
                await session.flush()

        return {"ok": True, "cashback": cashback, "cashback_pct": cashback_pct}