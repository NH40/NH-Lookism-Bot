from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.clan import Clan, ClanMember
from app.models.user import User
from app.constants.clan import CLAN_DONAT_PACKAGES_MAP


class ClanDonatService:

    async def apply_clan_donat(
        self, session: AsyncSession, clan: Clan, package_id: str
    ) -> dict:
        pkg = CLAN_DONAT_PACKAGES_MAP.get(package_id)
        if not pkg:
            return {"ok": False, "reason": "Пакет не найден"}

        clan.donat_income_pct += pkg.income_pct
        clan.donat_ticket_pct += pkg.ticket_pct
        clan.donat_train_pct  += pkg.train_pct

        members_r = await session.execute(
            select(ClanMember).where(ClanMember.clan_id == clan.id)
        )
        members = members_r.scalars().all()
        user_ids = [m.user_id for m in members]
        users_r = await session.execute(select(User).where(User.id.in_(user_ids)))
        users = users_r.scalars().all()
        for u in users:
            u.clan_donat_income_bonus = clan.donat_income_pct
            u.clan_donat_ticket_bonus = clan.donat_ticket_pct
            u.clan_donat_train_bonus  = clan.donat_train_pct

        await session.flush()
        return {"ok": True, "package": pkg}

    async def reset_clan_donat(self, session: AsyncSession, clan: Clan) -> dict:
        clan.donat_income_pct = 0
        clan.donat_ticket_pct = 0
        clan.donat_train_pct  = 0

        members_r = await session.execute(
            select(ClanMember).where(ClanMember.clan_id == clan.id)
        )
        members = members_r.scalars().all()
        user_ids = [m.user_id for m in members]
        users_r = await session.execute(select(User).where(User.id.in_(user_ids)))
        users = users_r.scalars().all()
        for u in users:
            u.clan_donat_income_bonus = 0
            u.clan_donat_ticket_bonus = 0
            u.clan_donat_train_bonus  = 0

        await session.flush()
        return {"ok": True}
