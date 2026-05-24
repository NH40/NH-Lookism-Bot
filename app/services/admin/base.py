from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
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
        # Один запрос вместо 4
        from sqlalchemy import case, literal
        for phase in ["gang", "king", "fist", "emperor"]:
            count = await session.scalar(
                select(func.count(User.id)).where(User.phase == phase)
            )
            phases[phase] = count
        with_power = await session.scalar(
            select(func.count(User.id)).where(User.combat_power > 0)
        )
        result = {"total": total, "phases": phases, "with_power": with_power}
        try:
            await r.setex("admin:stats", 60, json.dumps(result, ensure_ascii=False))
        except Exception:
            pass
        return result

    async def delete_user(self, session: AsyncSession, user: User) -> None:
        from app.services.prestige_service import prestige_service
        from app.models.title import UserAchievement, UserDonatTitle
        from app.models.skill import UserMastery
        from app.models.clan import ClanMember
        from sqlalchemy import delete as sa_delete

        await prestige_service._reset_progress(session, user, keep_ui=False)

        await session.execute(sa_delete(UserAchievement).where(UserAchievement.user_id == user.id))
        await session.execute(sa_delete(UserDonatTitle).where(UserDonatTitle.user_id == user.id))
        await session.execute(sa_delete(UserMastery).where(UserMastery.user_id == user.id))
        await session.execute(sa_delete(ClanMember).where(ClanMember.user_id == user.id))
        await session.delete(user)
        await session.flush()
