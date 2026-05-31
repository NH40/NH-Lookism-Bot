"""Управление активными слотами колоды (UserDeck)."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.character import UserCharacter
from app.models.card_deck import UserDeck


class DeckSlotService:
    """CRUD для слотов активной колоды игрока."""

    async def get_deck(self, session: AsyncSession, user_id: int) -> list[UserDeck]:
        result = await session.execute(
            select(UserDeck).where(UserDeck.user_id == user_id).order_by(UserDeck.slot)
        )
        return list(result.scalars().all())

    async def get_deck_char_ids(self, session: AsyncSession, user_id: int) -> set[int]:
        result = await session.execute(
            select(UserDeck.char_id).where(UserDeck.user_id == user_id)
        )
        return set(result.scalars().all())

    async def set_deck_slot(
        self, session: AsyncSession, user: User, slot: int, uc_id: int
    ) -> dict:
        """Поставить карточку uc_id в слот 1-5."""
        if slot < 1 or slot > 5:
            return {"ok": False, "reason": "Слот должен быть от 1 до 5"}

        uc = await session.get(UserCharacter, uc_id)
        if not uc or uc.user_id != user.id:
            return {"ok": False, "reason": "Карточка не найдена"}

        # Если карточка уже в другом слоте — убираем её оттуда
        old_slot_row = await session.scalar(
            select(UserDeck).where(
                UserDeck.user_id == user.id,
                UserDeck.char_id == uc_id,
            )
        )
        if old_slot_row:
            await session.delete(old_slot_row)

        # Очищаем целевой слот если занят
        existing = await session.scalar(
            select(UserDeck).where(
                UserDeck.user_id == user.id,
                UserDeck.slot == slot,
            )
        )
        if existing:
            await session.delete(existing)

        # flush до insert — гарантирует порядок DELETE→INSERT в БД
        await session.flush()
        session.add(UserDeck(user_id=user.id, slot=slot, char_id=uc_id))
        await session.flush()
        return {"ok": True}

    async def clear_deck_slot(self, session: AsyncSession, user: User, slot: int) -> dict:
        row = await session.scalar(
            select(UserDeck).where(
                UserDeck.user_id == user.id,
                UserDeck.slot == slot,
            )
        )
        if row:
            await session.delete(row)
            await session.flush()
        return {"ok": True}

    async def clear_all_slots(self, session: AsyncSession, user_id: int) -> None:
        rows = (await session.execute(
            select(UserDeck).where(UserDeck.user_id == user_id)
        )).scalars().all()
        for row in rows:
            await session.delete(row)
        await session.flush()


deck_slot_service = DeckSlotService()
