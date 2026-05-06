from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.clan import ClanMember
from app.services.clan.base import ClanBaseService


class ClanExchangeService(ClanBaseService):

    async def exchange_resource(
        self, session: AsyncSession,
        from_user: User, to_user: User,
        resource_type: str, amount: int, meta: dict | None = None
    ) -> dict:
        if amount <= 0:
            return {"ok": False, "reason": "Количество должно быть больше 0"}

        if resource_type == "coins":
            if from_user.nh_coins < amount:
                return {"ok": False, "reason": "Недостаточно NHCoin"}
            from_user.nh_coins -= amount
            to_user.nh_coins += amount

        elif resource_type == "tickets":
            if from_user.tickets < amount:
                return {"ok": False, "reason": f"Недостаточно тикетов (есть {from_user.tickets})"}
            from_user.tickets -= amount
            to_user.tickets += amount

        elif resource_type == "mastery_points":
            if from_user.mastery_points < amount:
                return {"ok": False, "reason": "Недостаточно очков мастерства"}
            from_user.mastery_points -= amount
            to_user.mastery_points += amount

        elif resource_type == "ui_fragments":
            if from_user.ui_fragments < amount:
                return {"ok": False, "reason": "Недостаточно фрагментов УИ"}
            from_user.ui_fragments -= amount
            to_user.ui_fragments += amount

        elif resource_type == "path_points":
            if from_user.skill_path_points < amount:
                return {"ok": False, "reason": "Недостаточно очков пути"}
            from_user.skill_path_points -= amount
            to_user.skill_path_points += amount

        elif resource_type == "squad":
            return await self._exchange_squad(session, from_user, to_user, amount, meta)

        elif resource_type == "character":
            return await self._exchange_character(session, from_user, to_user, meta)

        await session.flush()
        return {"ok": True}

    async def _exchange_squad(self, session, from_user, to_user, amount, meta):
        from app.models.squad_member import SquadMember
        rank = meta.get("rank") if meta else None
        q = select(SquadMember).where(SquadMember.user_id == from_user.id)
        if rank:
            q = q.where(SquadMember.rank == rank)
        q = q.limit(amount)
        result = await session.execute(q)
        members = result.scalars().all()
        if len(members) < amount:
            return {"ok": False, "reason": f"Недостаточно статистов (есть {len(members)})"}
        for m in members:
            m.user_id = to_user.id
        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, from_user)
        await squad_repo.update_user_combat_power(session, to_user)
        await session.flush()
        return {"ok": True}

    async def _exchange_character(self, session, from_user, to_user, meta):
        char_id = meta.get("char_id") if meta else None
        if not char_id:
            return {"ok": False, "reason": "Не указан персонаж"}
        from app.models.character import UserCharacter
        char = await session.scalar(
            select(UserCharacter).where(UserCharacter.id == char_id, UserCharacter.user_id == from_user.id)
        )
        if not char:
            return {"ok": False, "reason": "Персонаж не найден"}
        char.user_id = to_user.id
        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, from_user)
        await squad_repo.update_user_combat_power(session, to_user)
        await session.flush()
        return {"ok": True}