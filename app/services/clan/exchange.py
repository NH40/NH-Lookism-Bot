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

        if resource_type == "coins":
            if amount <= 0:
                return {"ok": False, "reason": "Количество должно быть больше 0"}
            if from_user.nh_coins < amount:
                return {"ok": False, "reason": "Недостаточно NHCoin"}
            from_user.nh_coins -= amount
            to_user.nh_coins += amount

        elif resource_type == "tickets":
            if amount <= 0:
                return {"ok": False, "reason": "Количество должно быть больше 0"}
            if from_user.tickets < amount:
                return {"ok": False, "reason": f"Недостаточно тикетов (есть {from_user.tickets})"}
            from app.config.game_balance import ticket_hard_cap
            cap = ticket_hard_cap(to_user)
            if to_user.tickets >= cap:
                return {"ok": False, "reason": f"У получателя хранилище полно ({to_user.tickets}/{cap})"}
            actual = min(amount, cap - to_user.tickets)
            from_user.tickets -= actual
            to_user.tickets += actual

        elif resource_type == "mastery_points":
            if amount <= 0:
                return {"ok": False, "reason": "Количество должно быть больше 0"}
            if from_user.mastery_points < amount:
                return {"ok": False, "reason": "Недостаточно очков мастерства"}
            from_user.mastery_points -= amount
            to_user.mastery_points += amount

        elif resource_type == "ui_fragments":
            if amount <= 0:
                return {"ok": False, "reason": "Количество должно быть больше 0"}
            if from_user.ui_fragments < amount:
                return {"ok": False, "reason": "Недостаточно фрагментов УИ"}
            from_user.ui_fragments -= amount
            to_user.ui_fragments += amount

        elif resource_type == "alchemy_fragments":
            if amount <= 0:
                return {"ok": False, "reason": "Количество должно быть больше 0"}
            if from_user.alchemy_fragments < amount:
                return {"ok": False, "reason": "Недостаточно фрагментов алхимии"}
            from_user.alchemy_fragments -= amount
            to_user.alchemy_fragments += amount

        elif resource_type == "path_fragments":
            if amount <= 0:
                return {"ok": False, "reason": "Количество должно быть больше 0"}
            if (from_user.path_fragments or 0) < amount:
                return {"ok": False, "reason": "Недостаточно фрагментов Пути"}
            from_user.path_fragments = (from_user.path_fragments or 0) - amount
            to_user.path_fragments = (to_user.path_fragments or 0) + amount

        elif resource_type == "card_dust":
            if amount <= 0:
                return {"ok": False, "reason": "Количество должно быть больше 0"}
            if (from_user.card_dust or 0) < amount:
                return {"ok": False, "reason": f"Недостаточно пыли карт (есть {from_user.card_dust or 0})"}
            from_user.card_dust = (from_user.card_dust or 0) - amount
            to_user.card_dust = (to_user.card_dust or 0) + amount

        elif resource_type == "path_points":
            if amount <= 0:
                return {"ok": False, "reason": "Количество должно быть больше 0"}
            if from_user.skill_path_points < amount:
                return {"ok": False, "reason": "Недостаточно очков пути"}
            from_user.skill_path_points -= amount
            to_user.skill_path_points += amount

        elif resource_type == "squad":
            if amount <= 0:
                return {"ok": False, "reason": "Количество должно быть больше 0"}
            return await self._exchange_squad(session, from_user, to_user, amount, meta)

        elif resource_type == "squad_all":
            return await self._exchange_squad_all(session, from_user, to_user, meta)

        elif resource_type == "character":
            return await self._exchange_character(session, from_user, to_user, meta)

        elif resource_type == "character_name":
            if amount <= 0:
                return {"ok": False, "reason": "Количество должно быть больше 0"}
            return await self._exchange_characters_by_name(session, from_user, to_user, amount, meta)

        elif resource_type == "character_rank":
            return await self._exchange_characters_by_rank(session, from_user, to_user, meta)

        else:
            return {"ok": False, "reason": "Неизвестный тип ресурса"}

        await session.flush()
        return {"ok": True}

    # ── Статисты ────────────────────────────────────────────────────────────

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
        await self._recalc_power(session, from_user, to_user)
        return {"ok": True}

    async def _exchange_squad_all(self, session, from_user, to_user, meta):
        from app.models.squad_member import SquadMember
        rank = meta.get("rank") if meta else None
        if not rank:
            return {"ok": False, "reason": "Не указан ранг"}
        result = await session.execute(
            select(SquadMember)
            .where(SquadMember.user_id == from_user.id, SquadMember.rank == rank)
        )
        members = result.scalars().all()
        if not members:
            return {"ok": False, "reason": f"Нет статистов ранга {rank}"}
        for m in members:
            m.user_id = to_user.id
        await self._recalc_power(session, from_user, to_user)
        return {"ok": True}

    # ── Персонажи ───────────────────────────────────────────────────────────

    async def _remove_from_deck(self, session, user_id: int, char_ids: list[int]) -> None:
        """Удаляет карточки из активной колоды перед передачей."""
        from app.models.card_deck import UserDeck
        if not char_ids:
            return
        rows = (await session.execute(
            select(UserDeck).where(
                UserDeck.user_id == user_id,
                UserDeck.char_id.in_(char_ids),
            )
        )).scalars().all()
        for row in rows:
            await session.delete(row)

    async def _exchange_character(self, session, from_user, to_user, meta):
        char_id = meta.get("char_id") if meta else None
        if not char_id:
            return {"ok": False, "reason": "Не указан персонаж"}
        from app.models.character import UserCharacter
        char = await session.scalar(
            select(UserCharacter).where(
                UserCharacter.id == char_id,
                UserCharacter.user_id == from_user.id,
            )
        )
        if not char:
            return {"ok": False, "reason": "Персонаж не найден"}
        await self._remove_from_deck(session, from_user.id, [char.id])
        char.user_id = to_user.id
        await self._recalc_power(session, from_user, to_user)
        return {"ok": True}

    async def _exchange_characters_by_name(self, session, from_user, to_user, amount, meta):
        char_name = meta.get("char_name") if meta else None
        if not char_name:
            return {"ok": False, "reason": "Не указан персонаж"}
        from app.models.character import UserCharacter
        result = await session.execute(
            select(UserCharacter)
            .where(UserCharacter.user_id == from_user.id, UserCharacter.character_id == char_name)
            .limit(amount)
        )
        chars = result.scalars().all()
        if len(chars) < amount:
            return {"ok": False, "reason": f"Недостаточно «{char_name}» (есть {len(chars)})"}
        await self._remove_from_deck(session, from_user.id, [c.id for c in chars])
        for c in chars:
            c.user_id = to_user.id
        await self._recalc_power(session, from_user, to_user)
        return {"ok": True}

    async def _exchange_characters_by_rank(self, session, from_user, to_user, meta):
        rank = meta.get("rank") if meta else None
        if not rank:
            return {"ok": False, "reason": "Не указан ранг"}
        from app.models.character import UserCharacter
        result = await session.execute(
            select(UserCharacter)
            .where(UserCharacter.user_id == from_user.id, UserCharacter.rank == rank)
        )
        chars = result.scalars().all()
        if not chars:
            return {"ok": False, "reason": f"Нет персонажей ранга {rank}"}
        await self._remove_from_deck(session, from_user.id, [c.id for c in chars])
        for c in chars:
            c.user_id = to_user.id
        await self._recalc_power(session, from_user, to_user)
        return {"ok": True}

    # ── Вспомогательные ─────────────────────────────────────────────────────

    async def _recalc_power(self, session, *users):
        from app.repositories.squad_repo import squad_repo
        for u in users:
            await squad_repo.update_user_combat_power(session, u)
        await session.flush()
