from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.clan import Clan, ClanMember


class ClanBaseService:

    async def get_user_clan(self, session: AsyncSession, user_id: int) -> Clan | None:
        member = await session.scalar(
            select(ClanMember).where(ClanMember.user_id == user_id)
        )
        if not member:
            return None
        return await session.scalar(select(Clan).where(Clan.id == member.clan_id))

    async def get_clan_members(self, session: AsyncSession, clan_id: int) -> list:
        result = await session.execute(
            select(ClanMember).where(ClanMember.clan_id == clan_id)
        )
        return result.scalars().all()

    async def recalc_power(self, session: AsyncSession, clan: Clan) -> None:
        members = await self.get_clan_members(session, clan.id)
        user_ids = [m.user_id for m in members]
        if not user_ids:
            clan.combat_power = 0
            await session.flush()
            return
        total = await session.scalar(
            select(func.sum(User.combat_power)).where(User.id.in_(user_ids))
        )
        clan.combat_power = total or 0
        await session.flush()

    async def create_clan(self, session: AsyncSession, user: User, name: str) -> dict:
        existing_member = await session.scalar(
            select(ClanMember).where(ClanMember.user_id == user.id)
        )
        if existing_member:
            return {"ok": False, "reason": "Вы уже состоите в клане"}
        name = name.strip()
        if len(name) < 2 or len(name) > 32:
            return {"ok": False, "reason": "Название от 2 до 32 символов"}
        existing = await session.scalar(select(Clan).where(Clan.name == name))
        if existing:
            return {"ok": False, "reason": "Клан с таким названием уже существует"}
        clan = Clan(name=name, owner_id=user.id, combat_power=user.combat_power)
        session.add(clan)
        await session.flush()
        member = ClanMember(clan_id=clan.id, user_id=user.id, rank="owner")
        session.add(member)
        await session.flush()
        return {"ok": True, "clan_id": clan.id, "name": name}

    async def get_top_clans(self, session: AsyncSession, limit: int = 10) -> list[Clan]:
        result = await session.execute(
            select(Clan).order_by(Clan.combat_power.desc()).limit(limit)
        )
        return result.scalars().all()

    async def transfer_ownership(self, session: AsyncSession, clan: Clan, owner: User, new_owner_id: int) -> dict:
        if clan.owner_id != owner.id:
            return {"ok": False, "reason": "Только владелец может передать права"}
        member = await session.scalar(
            select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == new_owner_id)
        )
        if not member:
            return {"ok": False, "reason": "Игрок не в клане"}
        clan.owner_id = new_owner_id
        await session.flush()
        return {"ok": True}

    async def rename_clan(self, session: AsyncSession, clan: Clan, owner: User, new_name: str) -> dict:
        if clan.owner_id != owner.id:
            return {"ok": False, "reason": "Только владелец может переименовать"}
        new_name = new_name.strip()
        if len(new_name) < 2 or len(new_name) > 32:
            return {"ok": False, "reason": "Название от 2 до 32 символов"}
        existing = await session.scalar(select(Clan).where(Clan.name == new_name))
        if existing:
            return {"ok": False, "reason": "Такое название уже занято"}
        clan.name = new_name
        await session.flush()
        return {"ok": True}

    async def delete_clan(self, session: AsyncSession, clan: Clan, owner: User) -> dict:
        if clan.owner_id != owner.id:
            return {"ok": False, "reason": "Только владелец может удалить клан"}
        members = await self.get_clan_members(session, clan.id)
        for m in members:
            await session.delete(m)
        await session.delete(clan)
        await session.flush()
        return {"ok": True}

    async def kick_member(self, session: AsyncSession, clan: Clan, owner: User, target_user_id: int) -> dict:
        if clan.owner_id != owner.id:
            return {"ok": False, "reason": "Только владелец может выгонять"}
        if target_user_id == owner.id:
            return {"ok": False, "reason": "Нельзя выгнать себя"}
        member = await session.scalar(
            select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == target_user_id)
        )
        if not member:
            return {"ok": False, "reason": "Игрок не в клане"}
        await session.delete(member)
        kicked_user = await session.scalar(select(User).where(User.id == target_user_id))
        if kicked_user:
            await self._remove_clan_bonuses_from_user(session, kicked_user)
        await self.recalc_power(session, clan)
        await session.flush()
        return {"ok": True}

    async def leave_clan(self, session: AsyncSession, user: User, transfer_to_id: int | None = None) -> dict:
        member = await session.scalar(select(ClanMember).where(ClanMember.user_id == user.id))
        if not member:
            return {"ok": False, "reason": "Вы не в клане"}
        clan = await session.scalar(select(Clan).where(Clan.id == member.clan_id))
        if clan.owner_id == user.id:
            members = await self.get_clan_members(session, clan.id)
            other_members = [m for m in members if m.user_id != user.id]
            if other_members and not transfer_to_id:
                return {"ok": False, "reason": "Вы владелец — сначала передайте права", "need_transfer": True}
            if transfer_to_id:
                clan.owner_id = transfer_to_id
            if not other_members:
                await session.delete(clan)
                await session.delete(member)
                await session.flush()
                return {"ok": True, "clan_deleted": True}
        await session.delete(member)
        await self._remove_clan_bonuses_from_user(session, user)
        await self.recalc_power(session, clan)
        await session.flush()
        return {"ok": True, "clan_deleted": False}

    async def _apply_clan_bonuses(self, session: AsyncSession, clan: Clan) -> None:
        from app.services.business_service import business_service
        members = await self.get_clan_members(session, clan.id)
        user_ids = [m.user_id for m in members]
        users = (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        for u in users:
            u.clan_income_bonus = clan.bonus_income_pct
            u.clan_ticket_bonus = clan.bonus_ticket_pct
            u.clan_train_bonus = clan.bonus_train_pct
            u.clan_donat_income_bonus = clan.donat_income_pct
            u.clan_donat_ticket_bonus = clan.donat_ticket_pct
            u.clan_donat_train_bonus = clan.donat_train_pct
            await business_service._recalc_income(session, u)

    async def _remove_clan_bonuses_from_user(self, session: AsyncSession, user: User) -> None:
        from app.services.business_service import business_service
        from app.services.clan.region import ClanRegionService
        user.clan_income_bonus = 0
        user.clan_ticket_bonus = 0
        user.clan_train_bonus = 0
        user.clan_donat_income_bonus = 0
        user.clan_donat_ticket_bonus = 0
        user.clan_donat_train_bonus = 0
        user.clan_vvip_level = 0
        await ClanRegionService().clear_region_bonuses_for_user(user)
        await business_service._recalc_income(session, user)

    async def _add_clan_bonuses_to_user(self, session: AsyncSession, clan: Clan, user: User) -> None:
        from app.services.business_service import business_service
        from app.services.clan.region import ClanRegionService
        user.clan_income_bonus = clan.bonus_income_pct
        user.clan_ticket_bonus = clan.bonus_ticket_pct
        user.clan_train_bonus = clan.bonus_train_pct
        user.clan_donat_income_bonus = clan.donat_income_pct
        user.clan_donat_ticket_bonus = clan.donat_ticket_pct
        user.clan_donat_train_bonus = clan.donat_train_pct
        user.clan_vvip_level = getattr(clan, "vvip_level", 0)
        await ClanRegionService().apply_region_bonuses_for_user(session, user, clan.id)
        await business_service._recalc_income(session, user)