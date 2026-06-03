"""Распыление карточек в пыль и слияние дубликатов."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.user import User
from app.models.character import UserCharacter
from app.models.card_deck import UserDeck
from app.data.characters import CHARACTERS
from app.constants.cards import LEVEL_MULTIPLIERS, FUSION_COST, DUST_PER_LEVEL, calc_dust, CARD_MAX_LEVEL, LEVEL_LABELS


def effective_power(base_power: int, level: int) -> int:
    return int(base_power * LEVEL_MULTIPLIERS.get(level, 1.0))


class FusionService:
    """Распыление и слияние карточек."""

    async def discard_card(self, session: AsyncSession, user: User, uc_id: int) -> dict:
        """Распылить одну карточку → пыль."""
        uc = await session.get(UserCharacter, uc_id)
        if not uc or uc.user_id != user.id:
            return {"ok": False, "reason": "Карточка не найдена"}

        in_deck = await session.scalar(
            select(UserDeck.id).where(
                UserDeck.user_id == user.id,
                UserDeck.char_id == uc_id,
            )
        )
        if in_deck:
            return {"ok": False, "reason": "Карточка в активной колоде — сначала уберите её"}

        dust = calc_dust(uc.rank, uc.level)
        char_name = uc.character_id
        level = uc.level

        await session.delete(uc)
        user.card_dust = getattr(user, "card_dust", 0) + dust
        await session.flush()

        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

        return {"ok": True, "dust": dust, "char_name": char_name, "level": level}

    async def count_chars(
        self, session: AsyncSession, user_id: int, character_id: str, level: int
    ) -> int:
        """Количество карточек (character_id, level) у игрока."""
        result = await session.scalar(
            select(func.count(UserCharacter.id)).where(
                UserCharacter.user_id == user_id,
                UserCharacter.character_id == character_id,
                UserCharacter.level == level,
            )
        )
        return result or 0

    async def fuse_cards(
        self, session: AsyncSession, user: User, character_id: str, current_level: int
    ) -> dict:
        """
        Слияние карточек:
          - 5 × Ур.0 → 1 × Ур.1
          - 3 × Ур.1 → 1 × Ур.2
          - 3 × Ур.2 → 1 × Ур.3
        Карточки из активной колоды не потребляются.
        """
        if current_level >= CARD_MAX_LEVEL:
            return {"ok": False, "reason": f"Уровень {CARD_MAX_LEVEL} — максимум. Выше некуда."}

        cost = FUSION_COST.get(current_level)
        if cost is None:
            return {"ok": False, "reason": "Неверный уровень"}

        # Карточки в активной колоде — не трогаем
        deck_ids = set(
            (await session.execute(
                select(UserDeck.char_id).where(UserDeck.user_id == user.id)
            )).scalars().all()
        )

        candidates = (await session.execute(
            select(UserCharacter).where(
                UserCharacter.user_id == user.id,
                UserCharacter.character_id == character_id,
                UserCharacter.level == current_level,
            ).order_by(UserCharacter.id).limit(cost * 2)  # берём с запасом
        )).scalars().all()

        available = [c for c in candidates if c.id not in deck_ids]
        if len(available) < cost:
            in_deck_cnt = sum(1 for c in candidates if c.id in deck_ids)
            hint = f" ({in_deck_cnt} в колоде — сначала замените)" if in_deck_cnt else ""
            return {
                "ok": False,
                "reason": f"Недостаточно карточек вне колоды: {len(available)}/{cost}{hint}",
            }

        to_consume = available[:cost]
        base_power = to_consume[0].base_power
        rank = to_consume[0].rank
        new_level = current_level + 1
        new_power = effective_power(base_power, new_level)

        for uc in to_consume:
            await session.delete(uc)

        new_card = UserCharacter(
            user_id=user.id,
            character_id=character_id,
            rank=rank,
            base_power=base_power,
            power=new_power,
            level=new_level,
        )
        session.add(new_card)
        await session.flush()

        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

        return {
            "ok": True,
            "new_level": new_level,
            "new_power": new_power,
            "char_name": character_id,
        }


    async def batch_fuse_all(
        self, session: AsyncSession, user: User
    ) -> dict:
        """
        Выполняет все возможные слияния за один проход.
        2 SELECT-запроса вместо 2×N.
        """
        deck_ids = set((await session.execute(
            select(UserDeck.char_id).where(UserDeck.user_id == user.id)
        )).scalars().all())

        all_chars = (await session.execute(
            select(UserCharacter).where(UserCharacter.user_id == user.id)
        )).scalars().all()

        # Строим словарь (char_id, level) → [cards outside deck]
        buckets: dict[tuple, list[UserCharacter]] = {}
        for c in all_chars:
            if c.id not in deck_ids:
                key = (c.character_id, c.level)
                buckets.setdefault(key, []).append(c)

        to_delete: list[UserCharacter] = []
        to_add: list[UserCharacter] = []
        fused_names: list[str] = []
        # Эфемерные карты: созданы в этом батче, ещё не сохранены в БД.
        # При цепочечном слиянии (Ур.0→Ур.1→Ур.2 за один проход)
        # эфемерная карта может быть сразу израсходована следующим шагом —
        # тогда отменяем её добавление вместо session.delete на несохранённый объект.
        ephemeral: set[int] = set()  # id() несохранённых карт
        MAX_ITER = 500

        for _ in range(MAX_ITER):
            # Ищем пару: высокие уровни приоритетнее
            target = None
            for (char_id, level), cards in sorted(
                buckets.items(), key=lambda x: (-x[0][1], -len(x[1]))
            ):
                cost = FUSION_COST.get(level)
                if cost and level < CARD_MAX_LEVEL and len(cards) >= cost:
                    target = (char_id, level, cost, cards)
                    break

            if not target:
                break

            char_id, level, cost, cards = target
            consumed = cards[:cost]
            buckets[(char_id, level)] = cards[cost:]

            base_power = consumed[0].base_power
            rank = consumed[0].rank
            new_level = level + 1
            new_power = effective_power(base_power, new_level)

            new_card = UserCharacter(
                user_id=user.id,
                character_id=char_id,
                rank=rank,
                base_power=base_power,
                power=new_power,
                level=new_level,
            )

            for c in consumed:
                if id(c) in ephemeral:
                    # Карта создана в этом батче — отменяем, не добавляем в to_delete
                    ephemeral.discard(id(c))
                    to_add.remove(c)
                else:
                    to_delete.append(c)

            to_add.append(new_card)
            ephemeral.add(id(new_card))
            buckets.setdefault((char_id, new_level), []).append(new_card)

            new_lbl = LEVEL_LABELS.get(new_level, f"Ур.{new_level}")
            fused_names.append(f"{char_id} → {new_lbl}")

        if not fused_names:
            return {"ok": True, "total": 0, "names": []}

        for c in to_delete:
            await session.delete(c)
        for c in to_add:
            session.add(c)

        await session.flush()

        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

        return {"ok": True, "total": len(fused_names), "names": fused_names}


fusion_service = FusionService()
