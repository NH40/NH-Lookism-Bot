import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sa_delete, update as sa_update
from app.models.user import User
from app.models.clan import ClanMember
from app.services.clan.base import ClanBaseService

logger = logging.getLogger(__name__)


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
            amount = actual

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

        elif resource_type == "business_fragments":
            if amount <= 0:
                return {"ok": False, "reason": "Количество должно быть больше 0"}
            if (from_user.business_fragments or 0) < amount:
                return {"ok": False, "reason": f"Недостаточно фрагментов бизнеса (есть {from_user.business_fragments or 0})"}
            from_user.business_fragments = (from_user.business_fragments or 0) - amount
            to_user.business_fragments = (to_user.business_fragments or 0) + amount

        elif resource_type == "war_points":
            if amount <= 0:
                return {"ok": False, "reason": "Количество должно быть больше 0"}
            if (from_user.war_points or 0) < amount:
                return {"ok": False, "reason": f"Недостаточно очков войны (есть {from_user.war_points or 0})"}
            from_user.war_points = (from_user.war_points or 0) - amount
            to_user.war_points = (to_user.war_points or 0) + amount

        else:
            return {"ok": False, "reason": "Неизвестный тип ресурса"}

        await session.flush()
        logger.info(
            "exchange: from_user=%d to_user=%d resource=%s amount=%d",
            from_user.id, to_user.id, resource_type, amount,
        )
        return {"ok": True, "amount": amount}

    # ── Статисты ────────────────────────────────────────────────────────────

    async def _exchange_squad(self, session, from_user, to_user, amount, meta):
        from app.models.squad_member import SquadMember
        from sqlalchemy import func as sqla_func
        rank = meta.get("rank") if meta else None

        cond = SquadMember.user_id == from_user.id
        if rank:
            cond = cond & (SquadMember.rank == rank)

        available = await session.scalar(select(sqla_func.count(SquadMember.id)).where(cond))
        if (available or 0) < amount:
            return {"ok": False, "reason": f"Недостаточно статистов (есть {available or 0})"}

        # Subquery вместо материализации ID в Python — нет огромного IN-списка
        subq = select(SquadMember.id).where(cond).limit(amount)
        await session.execute(
            sa_update(SquadMember)
            .where(SquadMember.id.in_(subq))
            .values(user_id=to_user.id)
            .execution_options(synchronize_session=False)
        )
        await self._recalc_power(session, from_user, to_user)
        logger.info("exchange: from_user=%d to_user=%d resource=squad amount=%d", from_user.id, to_user.id, amount)
        return {"ok": True}

    async def _exchange_squad_all(self, session, from_user, to_user, meta):
        from app.models.squad_member import SquadMember
        rank = meta.get("rank") if meta else None
        if not rank:
            return {"ok": False, "reason": "Не указан ранг"}
        from sqlalchemy import func
        count = await session.scalar(
            select(func.count(SquadMember.id))
            .where(SquadMember.user_id == from_user.id, SquadMember.rank == rank)
        )
        if not count:
            return {"ok": False, "reason": f"Нет статистов ранга {rank}"}
        await session.execute(
            sa_update(SquadMember)
            .where(SquadMember.user_id == from_user.id, SquadMember.rank == rank)
            .values(user_id=to_user.id)
            .execution_options(synchronize_session=False)
        )
        await self._recalc_power(session, from_user, to_user)
        logger.info("exchange: from_user=%d to_user=%d resource=squad_all rank=%s count=%d", from_user.id, to_user.id, rank, count)
        return {"ok": True}

    # ── Персонажи ───────────────────────────────────────────────────────────

    async def _remove_from_deck(self, session, user_id: int, char_ids: list[int]) -> None:
        """Удаляет карточки из активной колоды перед передачей."""
        from app.models.card_deck import UserDeck
        if not char_ids:
            return
        await session.execute(
            sa_delete(UserDeck).where(
                UserDeck.user_id == user_id,
                UserDeck.char_id.in_(char_ids),
            ).execution_options(synchronize_session=False)
        )

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
        logger.info("exchange: from_user=%d to_user=%d resource=character char_id=%d", from_user.id, to_user.id, char_id)
        return {"ok": True}

    async def _exchange_characters_by_name(self, session, from_user, to_user, amount, meta):
        char_name = meta.get("char_name") if meta else None
        if not char_name:
            return {"ok": False, "reason": "Не указан персонаж"}
        from app.models.character import UserCharacter
        ids = (await session.scalars(
            select(UserCharacter.id)
            .where(UserCharacter.user_id == from_user.id, UserCharacter.character_id == char_name)
            .limit(amount)
        )).all()
        if len(ids) < amount:
            return {"ok": False, "reason": f"Недостаточно «{char_name}» (есть {len(ids)})"}
        await self._remove_from_deck(session, from_user.id, ids)
        await session.execute(
            sa_update(UserCharacter)
            .where(UserCharacter.id.in_(ids))
            .values(user_id=to_user.id)
            .execution_options(synchronize_session=False)
        )
        await self._recalc_power(session, from_user, to_user)
        logger.info("exchange: from_user=%d to_user=%d resource=character_name char=%s amount=%d", from_user.id, to_user.id, char_name, len(ids))
        return {"ok": True}

    async def _exchange_characters_by_rank(self, session, from_user, to_user, meta):
        rank = meta.get("rank") if meta else None
        if not rank:
            return {"ok": False, "reason": "Не указан ранг"}
        from app.models.character import UserCharacter
        ids = (await session.scalars(
            select(UserCharacter.id)
            .where(UserCharacter.user_id == from_user.id, UserCharacter.rank == rank)
        )).all()
        if not ids:
            return {"ok": False, "reason": f"Нет персонажей ранга {rank}"}
        await self._remove_from_deck(session, from_user.id, ids)
        await session.execute(
            sa_update(UserCharacter)
            .where(UserCharacter.id.in_(ids))
            .values(user_id=to_user.id)
            .execution_options(synchronize_session=False)
        )
        await self._recalc_power(session, from_user, to_user)
        logger.info("exchange: from_user=%d to_user=%d resource=character_rank rank=%s count=%d", from_user.id, to_user.id, rank, len(ids))
        return {"ok": True}

    # ── Вспомогательные ─────────────────────────────────────────────────────

    async def _recalc_power(self, session, *users):
        from app.repositories.squad_repo import squad_repo
        for u in sorted(set(users), key=lambda x: x.id):
            await squad_repo.update_user_combat_power(session, u)
        await session.flush()
