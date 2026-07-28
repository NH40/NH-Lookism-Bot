"""Ячейки хранилища: открытие, хранение ресурсов, извлечение."""
import json

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.bank import StorageCell
from app.services.bank.storage_service import (
    storage_service, RESOURCE_ITEMS, OPEN_COST, FEE_PER_MINUTE, MAX_SLOTS
)
from app.utils.formatters import fmt_num
from app.utils.keyboards.common import back_kb
from app.utils.menu_media import safe_edit

router = Router()


class StorageFSM(StatesGroup):
    waiting_store_amount = State()


# ── Вспомогательные ──────────────────────────────────────────────────────────

def _cell_display(cell: StorageCell) -> str:
    if not cell.is_open:
        return f"🔒 Слот {cell.slot} — Закрыт ({fmt_num(OPEN_COST)} NHCoin)"
    if cell.item_type is None:
        return f"📭 Слот {cell.slot} — Пусто"
    label = RESOURCE_ITEMS.get(cell.item_type, (cell.item_type,))[0]
    data = json.loads(cell.item_data or "{}")
    amount = data.get("amount", "?")
    return f"📦 Слот {cell.slot} — {label}: {fmt_num(amount)}"


def _storage_kb(cells: list[StorageCell], user: User) -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    for cell in cells:
        if not cell.is_open:
            builder.row(InlineKeyboardButton(
                text=f"🔓 Открыть слот {cell.slot} ({fmt_num(OPEN_COST)} NHCoin)",
                callback_data=f"storage_open:{cell.slot}"
            ))
        elif cell.item_type is None:
            builder.row(InlineKeyboardButton(
                text=f"📥 Положить в слот {cell.slot}",
                callback_data=f"storage_store:{cell.slot}"
            ))
        else:
            label = RESOURCE_ITEMS.get(cell.item_type, (cell.item_type,))[0]
            data = json.loads(cell.item_data or "{}")
            amount = data.get("amount", 0)
            builder.row(InlineKeyboardButton(
                text=f"📤 Достать из слота {cell.slot} ({label}: {fmt_num(amount)})",
                callback_data=f"storage_retrieve:{cell.slot}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_menu"))
    return builder.as_markup()


# ── Главное меню хранилища ────────────────────────────────────────────────────

@router.callback_query(F.data == "bank_storage")
async def cb_bank_storage(cb: CallbackQuery, session: AsyncSession, user: User):
    cells = await storage_service.ensure_cells(session, user.id)
    open_count = sum(1 for c in cells if c.is_open)
    non_empty = sum(1 for c in cells if c.is_open and c.item_type is not None)

    lines = [
        "🗄 <b>Ячейки хранилища</b>\n",
        f"Открыто: {open_count}/{MAX_SLOTS} ячеек",
        f"Плата: {fmt_num(FEE_PER_MINUTE)} NHCoin/мин (за непустые ячейки)",
        f"Активных: {non_empty} ячеек\n",
        "— Содержимое сохраняется при сносе банды —\n",
    ]
    for cell in cells:
        lines.append(_cell_display(cell))

    await safe_edit(cb, "\n".join(lines), _storage_kb(cells, user))
    await cb.answer()


# ── Открыть ячейку ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("storage_open:"))
async def cb_storage_open(cb: CallbackQuery, session: AsyncSession, user: User):
    slot = int(cb.data.split(":")[1])
    ok, err = await storage_service.open_cell(session, user, slot)
    if not ok:
        await cb.answer(err, show_alert=True)
        return
    await cb.answer(f"✅ Слот {slot} открыт!", show_alert=True)
    # Обновим меню
    cells = await storage_service.get_cells(session, user.id)
    open_count = sum(1 for c in cells if c.is_open)
    non_empty = sum(1 for c in cells if c.is_open and c.item_type is not None)
    lines = [
        "🗄 <b>Ячейки хранилища</b>\n",
        f"Открыто: {open_count}/{MAX_SLOTS} ячеек",
        f"Плата: {fmt_num(FEE_PER_MINUTE)} NHCoin/мин (за непустые ячейки)",
        f"Активных: {non_empty} ячеек\n",
        "— Содержимое сохраняется при сносе банды —\n",
    ]
    for cell in cells:
        lines.append(_cell_display(cell))
    await safe_edit(cb, "\n".join(lines), _storage_kb(cells, user))


# ── Выбрать ресурс → ввести сумму ────────────────────────────────────────────

@router.callback_query(F.data.startswith("storage_store:"))
async def cb_storage_store(cb: CallbackQuery, user: User, state: FSMContext):
    slot = int(cb.data.split(":")[1])
    await state.set_state(StorageFSM.waiting_store_amount)
    await state.update_data(slot=slot)

    builder = InlineKeyboardBuilder()
    for res, (label, attr) in RESOURCE_ITEMS.items():
        balance = getattr(user, attr, 0)
        builder.row(InlineKeyboardButton(
            text=f"{label}: {fmt_num(balance)}",
            callback_data=f"storage_pick_res:{slot}:{res}"
        ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_storage"))
    await safe_edit(cb, f"📥 <b>Слот {slot} — выберите ресурс</b>\n\nЧто положить?", builder.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("storage_pick_res:"))
async def cb_storage_pick_res(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    parts = cb.data.split(":")
    slot = int(parts[1])
    res = parts[2]
    if res not in RESOURCE_ITEMS:
        await cb.answer("❌ Неизвестный ресурс.", show_alert=True)
        return

    label, attr = RESOURCE_ITEMS[res]
    balance = getattr(user, attr, 0)

    await state.set_state(StorageFSM.waiting_store_amount)
    await state.update_data(slot=slot, resource=res)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_storage"))
    await safe_edit(
        cb,
        f"📥 <b>Слот {slot} — {label}</b>\n\n"
        f"Баланс: {fmt_num(balance)}\n\n"
        f"Введите количество для хранения:",
        cancel_kb.as_markup(),
    )
    await cb.answer()


@router.message(StorageFSM.waiting_store_amount)
async def msg_storage_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    slot = data.get("slot", 1)
    resource = data.get("resource")
    await state.clear()

    if not resource:
        await message.answer("❌ Ресурс не выбран.", reply_markup=back_kb("bank_storage"), parse_mode="HTML")
        return

    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Введите целое число.", reply_markup=back_kb("bank_storage"), parse_mode="HTML")
        return

    ok, err = await storage_service.store_resource(session, user, slot, resource, amount)
    if not ok:
        await message.answer(err, reply_markup=back_kb("bank_storage"), parse_mode="HTML")
        return

    label = RESOURCE_ITEMS[resource][0]
    await message.answer(
        f"✅ <b>{fmt_num(amount)} {label}</b> помещено в слот {slot}.\n\n"
        f"Плата: {fmt_num(FEE_PER_MINUTE)} NHCoin/мин (снимается автоматически).",
        reply_markup=back_kb("bank_storage"),
        parse_mode="HTML",
    )


# ── Достать из ячейки ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("storage_retrieve:"))
async def cb_storage_retrieve(cb: CallbackQuery, session: AsyncSession, user: User):
    slot = int(cb.data.split(":")[1])
    cell = await storage_service.get_cell(session, user.id, slot)
    if not cell or not cell.item_type:
        await cb.answer("❌ Ячейка пуста.", show_alert=True)
        return

    data = json.loads(cell.item_data or "{}")
    amount = data.get("amount", 0)
    label = RESOURCE_ITEMS.get(cell.item_type, (cell.item_type,))[0]

    ok, err = await storage_service.retrieve_resource(session, user, slot)
    if not ok:
        await cb.answer(err, show_alert=True)
        return

    await cb.answer(f"✅ Получено: {fmt_num(amount)} {label}", show_alert=True)
    # Обновим меню
    cells = await storage_service.get_cells(session, user.id)
    open_count = sum(1 for c in cells if c.is_open)
    non_empty = sum(1 for c in cells if c.is_open and c.item_type is not None)
    lines = [
        "🗄 <b>Ячейки хранилища</b>\n",
        f"Открыто: {open_count}/{MAX_SLOTS} ячеек",
        f"Плата: {fmt_num(FEE_PER_MINUTE)} NHCoin/мин (за непустые ячейки)",
        f"Активных: {non_empty} ячеек\n",
        "— Содержимое сохраняется при сносе банды —\n",
    ]
    for c in cells:
        lines.append(_cell_display(c))
    await safe_edit(cb, "\n".join(lines), _storage_kb(cells, user))
