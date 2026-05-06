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
        return {"ok": True}