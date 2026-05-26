"""
Ячейки хранилища: 5 слотов, плата в минуту, сохраняются через снос банды.
"""
import json
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.bank import StorageCell
from app.models.user import User
from app.constants.bank import STORAGE_MAX_SLOTS, STORAGE_OPEN_COST, STORAGE_FEE_PER_MINUTE

logger = logging.getLogger(__name__)

MAX_SLOTS      = STORAGE_MAX_SLOTS
OPEN_COST      = STORAGE_OPEN_COST
FEE_PER_MINUTE = STORAGE_FEE_PER_MINUTE

# Допустимые типы ресурсов для хранения
RESOURCE_ITEMS = {
    "nh_coins":          ("💰 NHCoin",         "nh_coins"),
    "tickets":           ("🎟 Тикеты",         "tickets"),
    "card_dust":         ("🌫 Пыль карт",      "card_dust"),
    "ui_fragments":      ("🔮 Фрагм. УИ",      "ui_fragments"),
    "alchemy_fragments": ("🧪 Фрагм. алхимии", "alchemy_fragments"),
    "path_fragments":    ("🩺 Фрагм. пути",    "path_fragments"),
    "mastery_points":    ("🎯 Очки мастерства","mastery_points"),
}


class StorageService:

    # ── Получить все ячейки игрока ─────────────────────────────────────────────

    async def get_cells(self, session: AsyncSession, user_id: int) -> list[StorageCell]:
        r = await session.execute(
            select(StorageCell).where(StorageCell.user_id == user_id)
            .order_by(StorageCell.slot)
        )
        return r.scalars().all()

    async def get_cell(
        self, session: AsyncSession, user_id: int, slot: int
    ) -> StorageCell | None:
        r = await session.execute(
            select(StorageCell).where(
                and_(StorageCell.user_id == user_id, StorageCell.slot == slot)
            )
        )
        return r.scalar_one_or_none()

    async def ensure_cells(self, session: AsyncSession, user_id: int) -> list[StorageCell]:
        """Создать строки для всех 5 слотов если их нет."""
        cells = await self.get_cells(session, user_id)
        existing_slots = {c.slot for c in cells}
        for slot in range(1, MAX_SLOTS + 1):
            if slot not in existing_slots:
                session.add(StorageCell(user_id=user_id, slot=slot, is_open=False))
        await session.flush()
        return await self.get_cells(session, user_id)

    # ── Открыть ячейку ────────────────────────────────────────────────────────

    async def open_cell(
        self, session: AsyncSession, user: User, slot: int
    ) -> tuple[bool, str]:
        cells = await self.ensure_cells(session, user.id)
        cell = next((c for c in cells if c.slot == slot), None)
        if not cell:
            return False, "❌ Ячейка не найдена."
        if cell.is_open:
            return False, "❌ Ячейка уже открыта."
        if user.nh_coins < OPEN_COST:
            return False, f"❌ Нужно {OPEN_COST:,} NHCoin для открытия ячейки."

        user.nh_coins -= OPEN_COST
        cell.is_open = True
        cell.opened_at = datetime.now(timezone.utc)
        cell.last_fee_at = datetime.now(timezone.utc)
        await session.flush()
        return True, ""

    # ── Положить ресурс ───────────────────────────────────────────────────────

    async def store_resource(
        self, session: AsyncSession, user: User, slot: int,
        item_type: str, amount: int
    ) -> tuple[bool, str]:
        if item_type not in RESOURCE_ITEMS:
            return False, "❌ Нельзя хранить этот ресурс."
        if amount <= 0:
            return False, "❌ Количество должно быть > 0."

        cell = await self.get_cell(session, user.id, slot)
        if not cell or not cell.is_open:
            return False, "❌ Ячейка не открыта."
        if cell.item_type is not None:
            return False, "❌ Ячейка уже занята. Сначала достаньте содержимое."

        attr = RESOURCE_ITEMS[item_type][1]
        balance = getattr(user, attr, 0)
        if balance < amount:
            return False, f"❌ Недостаточно {RESOURCE_ITEMS[item_type][0]}."

        setattr(user, attr, balance - amount)
        cell.item_type = item_type
        cell.item_data = json.dumps({"amount": amount})
        cell.last_fee_at = datetime.now(timezone.utc)
        await session.flush()
        return True, ""

    # ── Достать ресурс ────────────────────────────────────────────────────────

    async def retrieve_resource(
        self, session: AsyncSession, user: User, slot: int
    ) -> tuple[bool, str]:
        cell = await self.get_cell(session, user.id, slot)
        if not cell or not cell.is_open:
            return False, "❌ Ячейка не открыта."
        if cell.item_type is None:
            return False, "❌ Ячейка пуста."
        if cell.item_type not in RESOURCE_ITEMS:
            return False, "❌ Неизвестный тип предмета (обратитесь в поддержку)."

        data = json.loads(cell.item_data or "{}")
        amount = data.get("amount", 0)
        attr = RESOURCE_ITEMS[cell.item_type][1]
        setattr(user, attr, getattr(user, attr, 0) + amount)

        cell.item_type = None
        cell.item_data = None
        await session.flush()
        return True, ""

    # ── Ежеминутная плата (вызывается из планировщика) ────────────────────────

    async def fee_tick(self, session: AsyncSession) -> None:
        """Снять плату за все непустые открытые ячейки."""
        from app.models.user import User as UserModel
        from sqlalchemy import select as sel

        # Берём только непустые ячейки
        r = await session.execute(
            sel(StorageCell).where(
                and_(StorageCell.is_open == True, StorageCell.item_type.isnot(None))
            )
        )
        cells = r.scalars().all()

        # Загружаем всех затронутых пользователей
        user_ids = list({c.user_id for c in cells})
        if not user_ids:
            return

        users_r = await session.execute(
            sel(UserModel).where(UserModel.id.in_(user_ids))
        )
        users_map: dict[int, UserModel] = {u.id: u for u in users_r.scalars().all()}

        for cell in cells:
            user = users_map.get(cell.user_id)
            if not user:
                continue
            if user.nh_coins >= FEE_PER_MINUTE:
                user.nh_coins -= FEE_PER_MINUTE
            else:
                # Не хватает монет → содержимое пропадает
                logger.info(
                    f"storage_fee: user {cell.user_id} slot {cell.slot} "
                    f"— не хватило монет, содержимое удалено"
                )
                cell.item_type = None
                cell.item_data = None

        await session.flush()


storage_service = StorageService()
