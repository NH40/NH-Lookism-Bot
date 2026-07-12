from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete as sa_delete
from app.models.user import User
from app.models.clan import Clan, ClanMember


class ClanBaseService:

    async def get_user_clan(self, session: AsyncSession, user_id: int) -> Clan | None:
        # Single JOIN instead of 2 separate queries
        return await session.scalar(
            select(Clan)
            .join(ClanMember, ClanMember.clan_id == Clan.id)
            .where(ClanMember.user_id == user_id)
        )

    async def get_clan_members(self, session: AsyncSession, clan_id: int) -> list:
        result = await session.execute(
            select(ClanMember).where(ClanMember.clan_id == clan_id)
        )
        return result.scalars().all()

    async def get_clan_member_count(self, session: AsyncSession, clan_id: int) -> int:
        """COUNT(*) без загрузки ORM-объектов."""
        return await session.scalar(
            select(func.count()).where(ClanMember.clan_id == clan_id)
        ) or 0

    async def get_clan_member_ids(self, session: AsyncSession, clan_id: int) -> list[int]:
        """Только user_id участников — без загрузки полных ORM-объектов."""
        result = await session.execute(
            select(ClanMember.user_id).where(ClanMember.clan_id == clan_id)
        )
        return list(result.scalars().all())

    async def recalc_power(self, session: AsyncSession, clan: Clan) -> None:
        # JOIN-субзапрос — без загрузки участников в память
        total = await session.scalar(
            select(func.sum(User.combat_power))
            .join(ClanMember, ClanMember.user_id == User.id)
            .where(ClanMember.clan_id == clan.id)
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
        # Старый владелец становится участником
        old_owner_member = await session.scalar(
            select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == owner.id)
        )
        if old_owner_member:
            old_owner_member.rank = "member"
        member.rank = "owner"
        clan.owner_id = new_owner_id
        await session.flush()
        # Переприменяем бонусы региона: новый владелец получает owner-бонусы
        from app.services.clan.region import ClanRegionService
        region = await ClanRegionService().get_clan_region(session, clan.id)
        if region:
            await ClanRegionService().apply_region_bonuses_for_clan(session, clan.id, region)
        return {"ok": True}

    async def admin_transfer_ownership(self, session: AsyncSession, clan: Clan, new_owner_id: int) -> dict:
        """Смена владельца клана администратором без проверки прав."""
        member = await session.scalar(
            select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == new_owner_id)
        )
        if not member:
            return {"ok": False, "reason": "Игрок не в клане"}
        old_owner_member = await session.scalar(
            select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == clan.owner_id)
        )
        if old_owner_member:
            old_owner_member.rank = "member"
        member.rank = "owner"
        clan.owner_id = new_owner_id
        await session.flush()
        from app.services.clan.region import ClanRegionService
        region = await ClanRegionService().get_clan_region(session, clan.id)
        if region:
            await ClanRegionService().apply_region_bonuses_for_clan(session, clan.id, region)
        return {"ok": True}

    async def rename_clan(self, session: AsyncSession, clan: Clan, user: User, new_name: str) -> dict:
        member = await session.scalar(
            select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == user.id)
        )
        rank = member.rank if member else "member"
        if clan.owner_id != user.id and rank != "deputy":
            return {"ok": False, "reason": "Только владелец или заместитель может переименовать"}
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
        # Bulk DELETE вместо цикла
        await session.execute(sa_delete(ClanMember).where(ClanMember.clan_id == clan.id))
        await session.delete(clan)
        await session.flush()
        return {"ok": True}

    async def kick_member(self, session: AsyncSession, clan: Clan, acting_user: User, target_user_id: int) -> dict:
        acting_member = await session.scalar(
            select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == acting_user.id)
        )
        acting_rank = acting_member.rank if acting_member else "member"
        if acting_rank not in ("owner", "deputy"):
            return {"ok": False, "reason": "Только владелец или заместитель может выгонять"}
        if target_user_id == acting_user.id:
            return {"ok": False, "reason": "Нельзя выгнать себя"}
        if acting_rank == "deputy" and target_user_id == clan.owner_id:
            return {"ok": False, "reason": "Заместитель не может выгнать владельца"}
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

    async def _apply_clan_bonuses(
        self, session: AsyncSession, clan: Clan,
        bonus_income_pct: int | None = None,
        bonus_ticket_pct: int | None = None,
        bonus_train_pct: int | None = None,
        ap_income_circles: int | None = None,
        ap_train_circles: int | None = None,
        ap_ticket_circles: int | None = None,
    ) -> None:
        """Применяет клановые бонусы ко всем участникам.

        Опциональные override-параметры позволяют вызвать это ДО того как
        соответствующие поля clan будут физически изменены — тогда порядок
        блокировок при флаше остаётся users->clan (как и everywhere else,
        см. squad_repo.update_user_combat_power), а не clan->users, что
        вызывало deadlock с конкурентными операциями по тем же двум строкам
        (например, emperor.py при дропе карты). Если параметр не передан —
        читается текущее значение clan.* как раньше.
        """
        from app.services.business_service import business_service
        from app.config.game_balance import CLAN_AP_INCOME_BONUS, CLAN_AP_TRAIN_BONUS, CLAN_AP_TICKET_BONUS
        # Загружаем только user_id — без полных ORM-объектов
        user_ids = await self.get_clan_member_ids(session, clan.id)
        if not user_ids:
            return
        users = (await session.execute(
            select(User).where(User.id.in_(user_ids)).order_by(User.id)
        )).scalars().all()

        income_pct = clan.bonus_income_pct if bonus_income_pct is None else bonus_income_pct
        ticket_pct = clan.bonus_ticket_pct if bonus_ticket_pct is None else bonus_ticket_pct
        train_pct = clan.bonus_train_pct if bonus_train_pct is None else bonus_train_pct
        income_circles = getattr(clan, "ap_income_circles", 0) if ap_income_circles is None else ap_income_circles
        train_circles = getattr(clan, "ap_train_circles", 0) if ap_train_circles is None else ap_train_circles
        ticket_circles = getattr(clan, "ap_ticket_circles", 0) if ap_ticket_circles is None else ap_ticket_circles

        ap_income = income_circles * CLAN_AP_INCOME_BONUS
        ap_train = train_circles * CLAN_AP_TRAIN_BONUS
        ap_ticket = ticket_circles * CLAN_AP_TICKET_BONUS
        for u in users:
            u.clan_income_bonus = income_pct + ap_income
            u.clan_ticket_bonus = ticket_pct + ap_ticket
            u.clan_train_bonus = train_pct + ap_train
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
        user.clan_region_income = 0
        await ClanRegionService().clear_region_bonuses_for_user(user)
        await business_service._recalc_income(session, user)

    async def _add_clan_bonuses_to_user(self, session: AsyncSession, clan: Clan, user: User) -> None:
        from app.services.business_service import business_service
        from app.services.clan.region import ClanRegionService
        from app.services.clan.buildings import ClanBuildingsService
        from app.config.game_balance import CLAN_AP_INCOME_BONUS, CLAN_AP_TRAIN_BONUS, CLAN_AP_TICKET_BONUS
        ap_income = getattr(clan, "ap_income_circles", 0) * CLAN_AP_INCOME_BONUS
        ap_train = getattr(clan, "ap_train_circles", 0) * CLAN_AP_TRAIN_BONUS
        ap_ticket = getattr(clan, "ap_ticket_circles", 0) * CLAN_AP_TICKET_BONUS
        user.clan_income_bonus = clan.bonus_income_pct + ap_income
        user.clan_ticket_bonus = clan.bonus_ticket_pct + ap_ticket
        user.clan_train_bonus = clan.bonus_train_pct + ap_train
        user.clan_donat_income_bonus = clan.donat_income_pct
        user.clan_donat_ticket_bonus = clan.donat_ticket_pct
        user.clan_donat_train_bonus = clan.donat_train_pct
        user.clan_vvip_level = getattr(clan, "vvip_level", 0)
        await ClanRegionService().apply_region_bonuses_for_user(session, user, clan.id)
        region = await ClanRegionService().get_clan_region(session, clan.id)
        if region:
            bld_svc = ClanBuildingsService()
            buildings = await bld_svc.get_clan_buildings(session, clan.id)
            user.clan_region_income = bld_svc.calc_total_income_per_member(buildings)
        else:
            user.clan_region_income = 0
        await business_service._recalc_income(session, user)
