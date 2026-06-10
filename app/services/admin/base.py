from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, not_, exists
from app.models.user import User
from app.services.title_service import title_service
from app.config.game_balance import TUI_MAX_TICKETS, DEFAULT_MAX_TICKETS


class AdminBaseService:

    async def find_user(self, session: AsyncSession, query: str) -> User | None:
        if query.lstrip("-").isdigit():
            r = await session.execute(select(User).where(User.tg_id == int(query)))
            u = r.scalar_one_or_none()
            if u:
                return u
        uname = query.lstrip("@")
        r = await session.execute(select(User).where(User.username == uname))
        u = r.scalar_one_or_none()
        if u:
            return u
        r = await session.execute(select(User).where(User.gang_name.ilike(f"%{query}%")))
        return r.scalar_one_or_none()

    async def give_coins(self, session: AsyncSession, user: User, amount: int) -> None:
        user.nh_coins += amount
        await session.flush()

    async def give_tickets(self, session: AsyncSession, user: User, count: int) -> None:
        user.tickets += count
        await session.flush()

    async def give_tui(self, session: AsyncSession, user: User) -> None:
        user.ultra_instinct = True
        user.true_ultra_instinct = True
        user.max_tickets = TUI_MAX_TICKETS
        await session.flush()

    async def remove_tui(self, session: AsyncSession, user: User) -> None:
        user.true_ultra_instinct = False
        user.max_tickets = DEFAULT_MAX_TICKETS
        await session.flush()

    async def give_all_titles(self, session: AsyncSession, user: User, admin_tg_id: int) -> int:
        return await title_service.grant_all_titles(session, user, admin_tg_id)

    async def remove_all_titles(self, session: AsyncSession, user: User) -> None:
        await title_service.revoke_all_titles(session, user)

    async def get_stats(self, session: AsyncSession) -> dict:
        """Статистика с кешированием на 60 секунд."""
        import json
        try:
            from app.services.cooldown_service import cooldown_service
            r = cooldown_service.redis
            cached = await r.get("admin:stats")
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        total = await session.scalar(select(func.count(User.id)))
        phases = {}
        from sqlalchemy import case, literal
        for phase in ["gang", "king", "fist", "emperor"]:
            count = await session.scalar(
                select(func.count(User.id)).where(User.phase == phase)
            )
            phases[phase] = count
        with_power = await session.scalar(
            select(func.count(User.id)).where(User.combat_power > 0)
        )
        with_donate = await session.scalar(
            select(func.count(User.id)).where(User.nh_donate > 0)
        )

        from app.models.title import UserDonatTitle
        from app.data.titles import DONAT_TITLES
        all_title_ids = [t.title_id for t in DONAT_TITLES]
        total_titles = len(all_title_ids)
        vvip_subq = (
            select(UserDonatTitle.user_id)
            .where(UserDonatTitle.title_id.in_(all_title_ids))
            .group_by(UserDonatTitle.user_id)
            .having(func.count(UserDonatTitle.title_id) >= total_titles)
            .subquery()
        )
        vvip_count = await session.scalar(
            select(func.count()).select_from(vvip_subq)
        )

        result = {
            "total": total,
            "phases": phases,
            "with_power": with_power,
            "with_donate": with_donate,
            "vvip_count": vvip_count,
        }
        try:
            await r.setex("admin:stats", 60, json.dumps(result, ensure_ascii=False))
        except Exception:
            pass
        return result

    def _zero_account_filter(self):
        """WHERE-условие для аккаунтов с 0 мощью, без доната и без престижа."""
        return and_(
            User.combat_power == 0,
            User.prestige_level == 0,
            User.nh_donate == 0,
            User.ui_is_donat.is_(False),
            User.donat_ui_potion.is_(False),
            User.donat_duel_cd.is_(False),
            User.med_genius_donat.is_(False),
        )

    async def count_zero_accounts(self, session: AsyncSession) -> int:
        from app.models.title import UserDonatTitle
        no_titles = not_(
            exists().where(UserDonatTitle.user_id == User.id)
        )
        return await session.scalar(
            select(func.count(User.id)).where(
                self._zero_account_filter(), no_titles
            )
        ) or 0

    async def delete_zero_accounts(self, session: AsyncSession) -> int:
        from app.models.title import UserDonatTitle, UserAchievement
        from app.models.skill import UserMastery
        from app.models.clan import Clan, ClanMember
        from sqlalchemy import delete as sa_delete

        no_titles = not_(
            exists().where(UserDonatTitle.user_id == User.id)
        )
        target_ids_result = await session.execute(
            select(User.id).where(self._zero_account_filter(), no_titles)
        )
        target_ids = [row[0] for row in target_ids_result.all()]
        if not target_ids:
            return 0

        # Убираем участников кланов, удаляем пустые кланы
        clan_ids_result = await session.execute(
            select(ClanMember.clan_id).where(ClanMember.user_id.in_(target_ids)).distinct()
        )
        affected_clan_ids = [row[0] for row in clan_ids_result.all()]
        await session.execute(sa_delete(ClanMember).where(ClanMember.user_id.in_(target_ids)))
        for clan_id in affected_clan_ids:
            remaining = await session.scalar(
                select(func.count(ClanMember.user_id)).where(ClanMember.clan_id == clan_id)
            )
            if (remaining or 0) == 0:
                await session.execute(sa_delete(Clan).where(Clan.id == clan_id))

        await session.execute(sa_delete(UserAchievement).where(UserAchievement.user_id.in_(target_ids)))
        await session.execute(sa_delete(UserDonatTitle).where(UserDonatTitle.user_id.in_(target_ids)))
        await session.execute(sa_delete(UserMastery).where(UserMastery.user_id.in_(target_ids)))
        await session.execute(sa_delete(User).where(User.id.in_(target_ids)))
        await session.flush()
        return len(target_ids)

    async def delete_user(self, session: AsyncSession, user: User) -> None:
        from app.services.prestige_service import prestige_service
        from app.models.title import UserAchievement, UserDonatTitle
        from app.models.skill import UserMastery
        from app.models.clan import Clan, ClanMember
        from sqlalchemy import delete as sa_delete, select, func

        await prestige_service._reset_progress(session, user, keep_ui=False)

        await session.execute(sa_delete(UserAchievement).where(UserAchievement.user_id == user.id))
        await session.execute(sa_delete(UserDonatTitle).where(UserDonatTitle.user_id == user.id))
        await session.execute(sa_delete(UserMastery).where(UserMastery.user_id == user.id))

        # Проверяем клан перед удалением участника
        member = await session.scalar(select(ClanMember).where(ClanMember.user_id == user.id))
        if member:
            clan_id = member.clan_id
            await session.execute(sa_delete(ClanMember).where(ClanMember.user_id == user.id))
            remaining = await session.scalar(
                select(func.count(ClanMember.user_id)).where(ClanMember.clan_id == clan_id)
            )
            if remaining == 0:
                await session.execute(sa_delete(Clan).where(Clan.id == clan_id))

        await session.delete(user)
        await session.flush()
