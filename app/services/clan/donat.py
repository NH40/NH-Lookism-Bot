from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.clan import Clan, ClanMember
from app.models.user import User
from app.constants.clan import CLAN_DONAT_PACKAGES_MAP, CLAN_DONAT_PACKAGES

VVIP_MAX_LEVEL = 5


class ClanDonatService:

    async def apply_clan_donat(
        self, session: AsyncSession, clan: Clan, package_id: str
    ) -> dict:
        pkg = CLAN_DONAT_PACKAGES_MAP.get(package_id)
        if not pkg:
            return {"ok": False, "reason": "Пакет не найден"}

        # Проверяем лимит кругов
        current_circles = getattr(clan, pkg.circles_field, 0)
        if current_circles >= pkg.max_circles:
            return {
                "ok": False,
                "reason": f"Достигнут максимум {pkg.max_circles} кругов для «{pkg.name}»"
            }

        setattr(clan, pkg.circles_field, current_circles + 1)
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

        # Пересчитываем income_per_minute для всех участников
        from app.services.business_service import business_service
        for u in users:
            await business_service._recalc_income(session, u)

        return {"ok": True, "package": pkg}

    async def _sync_vvip_to_members(
        self, session: AsyncSession, clan: Clan, users: list
    ) -> None:
        """Синхронизировать уровень VVIP клана на всех участников."""
        for u in users:
            u.clan_vvip_level = clan.vvip_level

    async def apply_full_level(self, session: AsyncSession, clan: Clan) -> dict:
        if clan.vvip_level >= VVIP_MAX_LEVEL:
            return {"ok": False, "reason": f"Достигнут максимальный уровень VVIP ({VVIP_MAX_LEVEL})"}

        for pkg in CLAN_DONAT_PACKAGES:
            clan.donat_income_pct += pkg.income_pct
            clan.donat_ticket_pct += pkg.ticket_pct
            clan.donat_train_pct  += pkg.train_pct
        clan.vvip_level += 1

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
        await self._sync_vvip_to_members(session, clan, users)

        await session.flush()

        from app.services.business_service import business_service
        for u in users:
            await business_service._recalc_income(session, u)

        return {"ok": True, "level": clan.vvip_level}

    async def reset_clan_donat(self, session: AsyncSession, clan: Clan) -> dict:
        clan.donat_income_pct = 0
        clan.donat_ticket_pct = 0
        clan.donat_train_pct  = 0
        clan.vvip_level       = 0
        # Сброс счётчиков кругов
        for pkg in CLAN_DONAT_PACKAGES:
            setattr(clan, pkg.circles_field, 0)

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
        await self._sync_vvip_to_members(session, clan, users)

        await session.flush()

        # Пересчитываем income_per_minute после сброса
        from app.services.business_service import business_service
        for u in users:
            await business_service._recalc_income(session, u)

        return {"ok": True}
