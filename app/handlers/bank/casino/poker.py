"""PvP-покер: меню, создание стола, лобби, вход, действия за столом."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.poker import PokerTable
from app.services.bank.casino.poker_service import poker_service
from app.services.bank.casino.poker_notify import notify_event
from app.services.cooldown_service import cooldown_service
from app.constants.poker import (
    POKER_MIN_PLAYERS, POKER_MAX_PLAYERS, POKER_BUY_IN_MIN, POKER_BUY_IN_MAX, POKER_WAIT_OPTIONS_SECONDS,
)
from app.utils.formatters import fmt_num
from app.utils.safe_edit import safe_edit
from app.utils.keyboards.common import back_kb

router = Router()


class PokerCreateFSM(StatesGroup):
    waiting_buyin = State()


class PokerRaiseFSM(StatesGroup):
    waiting_amount = State()


# ── Меню ──────────────────────────────────────────────────────────────────────

def _poker_menu_kb() -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Создать стол", callback_data="poker_create"))
    builder.row(InlineKeyboardButton(text="📋 Открытые столы", callback_data="poker_lobby"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_casino"))
    return builder.as_markup()


@router.callback_query(F.data == "poker_menu")
async def cb_poker_menu(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    text = (
        "🂡 <b>Покер (PvP)</b>\n\n"
        "Полноценный Texas Hold'em против других игроков — с торгами на префлопе, флопе, тёрне и ривере.\n\n"
        f"Игроков за столом: {POKER_MIN_PLAYERS}–{POKER_MAX_PLAYERS}\n"
        f"Вход: {fmt_num(POKER_BUY_IN_MIN)}–{fmt_num(POKER_BUY_IN_MAX)} NHCoin\n\n"
        "Создайте стол или присоединитесь к открытому."
    )
    await safe_edit(cb.message, text, reply_markup=_poker_menu_kb())
    await cb.answer()


def _lobby_card_text(table: PokerTable, joined_count: int) -> str:
    return (
        f"🂡 <b>Стол #{table.id}</b>\n\n"
        f"Вход: {fmt_num(table.buy_in)} NHCoin\n"
        f"Блайнды: {fmt_num(table.small_blind)}/{fmt_num(table.big_blind)}\n"
        f"Игроков: {joined_count}/{table.max_players}\n"
        f"Статус: ⏳ ожидание игроков..."
    )


def _lobby_card_kb(table: PokerTable) -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔗 Присоединиться", callback_data=f"poker_join:{table.id}"))
    builder.row(InlineKeyboardButton(text="❌ Отменить стол", callback_data=f"poker_cancel:{table.id}"))
    builder.row(InlineKeyboardButton(text="◀️ Покер", callback_data="poker_menu"))
    return builder.as_markup()


# ── Создание стола ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "poker_create")
async def cb_poker_create(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    await state.set_state(PokerCreateFSM.waiting_buyin)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="poker_menu"))
    await safe_edit(
        cb.message,
        f"🂡 <b>Создание стола</b>\n\n"
        f"Ваш баланс: {fmt_num(user.nh_coins)} NHCoin\n"
        f"Введите сумму входа (от {fmt_num(POKER_BUY_IN_MIN)} до {fmt_num(POKER_BUY_IN_MAX)}):",
        reply_markup=cancel_kb.as_markup(),
    )
    await cb.answer()


@router.message(PokerCreateFSM.waiting_buyin)
async def msg_poker_buyin(message: Message, session: AsyncSession, user: User, state: FSMContext):
    try:
        buy_in = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Введите целое число.", reply_markup=back_kb("poker_menu"), parse_mode="HTML")
        return

    if not (POKER_BUY_IN_MIN <= buy_in <= POKER_BUY_IN_MAX):
        await message.answer(
            f"❌ Сумма входа: от {fmt_num(POKER_BUY_IN_MIN)} до {fmt_num(POKER_BUY_IN_MAX)} NHCoin.",
            reply_markup=back_kb("poker_menu"), parse_mode="HTML",
        )
        return
    if buy_in > (user.nh_coins or 0):
        await message.answer("❌ Недостаточно NHCoin.", reply_markup=back_kb("poker_menu"), parse_mode="HTML")
        return

    await state.update_data(buy_in=buy_in)

    builder = InlineKeyboardBuilder()
    for n in range(POKER_MIN_PLAYERS, POKER_MAX_PLAYERS + 1):
        builder.button(text=str(n), callback_data=f"poker_create_players:{n}")
    builder.adjust(POKER_MAX_PLAYERS - POKER_MIN_PLAYERS + 1)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="poker_menu"))
    await message.answer(
        f"👥 Сколько игроков за столом? (вход: {fmt_num(buy_in)} NHCoin)",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("poker_create_players:"))
async def cb_poker_create_players(cb: CallbackQuery, state: FSMContext):
    n = int(cb.data.split(":")[1])
    await state.update_data(max_players=n)

    builder = InlineKeyboardBuilder()
    for sec in POKER_WAIT_OPTIONS_SECONDS:
        builder.button(text=f"{sec // 60} мин", callback_data=f"poker_create_wait:{sec}")
    builder.adjust(len(POKER_WAIT_OPTIONS_SECONDS))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="poker_menu"))
    await safe_edit(cb.message, "⏳ Сколько ждать других игроков?", reply_markup=builder.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("poker_create_wait:"))
async def cb_poker_create_wait(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    wait_seconds = int(cb.data.split(":")[1])
    data = await state.get_data()
    buy_in = data.get("buy_in")
    max_players = data.get("max_players")
    await state.clear()

    if buy_in is None or max_players is None:
        await cb.answer("❌ Сессия истекла, начните заново.", show_alert=True)
        return

    lock_key = cooldown_service.poker_create_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подождите...", show_alert=True)
        return

    result = await poker_service.create_table(session, user, buy_in, max_players, wait_seconds)
    if not result.get("ok"):
        await cb.answer(result["msg"], show_alert=True)
        return

    table = result["table"]
    await safe_edit(cb.message, _lobby_card_text(table, 1), reply_markup=_lobby_card_kb(table))
    await cb.answer("✅ Стол создан!")


# ── Лобби / вход ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "poker_lobby")
async def cb_poker_lobby(cb: CallbackQuery, session: AsyncSession, user: User):
    tables = await poker_service.list_open_tables(session, limit=10)
    if not tables:
        await safe_edit(cb.message, "📋 <b>Открытые столы</b>\n\nСейчас нет открытых столов.", reply_markup=back_kb("poker_menu"))
        await cb.answer()
        return

    builder = InlineKeyboardBuilder()
    for table in tables:
        players = await poker_service.get_players(session, table.id)
        builder.row(InlineKeyboardButton(
            text=f"Стол #{table.id} — вход {fmt_num(table.buy_in)} ({len(players)}/{table.max_players})",
            callback_data=f"poker_view:{table.id}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="poker_menu"))
    await safe_edit(cb.message, "📋 <b>Открытые столы</b>\n\nВыберите стол:", reply_markup=builder.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("poker_view:"))
async def cb_poker_view(cb: CallbackQuery, session: AsyncSession, user: User):
    table_id = int(cb.data.split(":")[1])
    table = await poker_service.get_table(session, table_id)
    if not table or table.status != "waiting":
        await cb.answer("❌ Стол недоступен.", show_alert=True)
        return
    players = await poker_service.get_players(session, table_id)
    await safe_edit(cb.message, _lobby_card_text(table, len(players)), reply_markup=_lobby_card_kb(table))
    await cb.answer()


@router.callback_query(F.data.startswith("poker_join:"))
async def cb_poker_join(cb: CallbackQuery, session: AsyncSession, user: User):
    table_id = int(cb.data.split(":")[1])

    lock_key = cooldown_service.poker_join_lock_key(table_id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подождите...", show_alert=True)
        return

    result = await poker_service.join_table(session, table_id, user)
    if not result.get("ok"):
        await cb.answer(result["msg"], show_alert=True)
        return

    table = result["table"]
    players = result["players"]

    if result["started"]:
        await safe_edit(
            cb.message,
            f"✅ Стол #{table.id} заполнен — раздача началась! Проверьте личные сообщения.",
            reply_markup=back_kb("poker_menu"),
        )
        await notify_event(cb.bot, session, result["start_result"])
    else:
        await safe_edit(cb.message, _lobby_card_text(table, len(players)), reply_markup=_lobby_card_kb(table))

    await cb.answer("✅ Вы за столом!")


@router.callback_query(F.data.startswith("poker_cancel:"))
async def cb_poker_cancel(cb: CallbackQuery, session: AsyncSession, user: User):
    table_id = int(cb.data.split(":")[1])
    result = await poker_service.creator_cancel(session, table_id, user.id)
    if not result.get("ok"):
        await cb.answer(result["msg"], show_alert=True)
        return

    await notify_event(cb.bot, session, result)
    await safe_edit(cb.message, f"❌ Стол #{table_id} отменён, вход возвращён.", reply_markup=back_kb("poker_menu"))
    await cb.answer()


# ── Действия за столом ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("poker_act:"))
async def cb_poker_act(cb: CallbackQuery, session: AsyncSession, user: User):
    _, table_id_str, action = cb.data.split(":")
    table_id = int(table_id_str)

    lock_key = cooldown_service.poker_action_lock_key(table_id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подождите...", show_alert=True)
        return

    table = await poker_service.get_table(session, table_id)
    if not table:
        await cb.answer("❌ Стол не найден.", show_alert=True)
        return

    result = await poker_service.apply_action(session, table, user.id, action)
    if not result.get("ok"):
        await cb.answer(result["msg"], show_alert=True)
        return

    await safe_edit(cb.message, "✅ Действие принято.", reply_markup=None)
    await notify_event(cb.bot, session, result)
    await cb.answer()


@router.callback_query(F.data.startswith("poker_bet_menu:"))
async def cb_poker_bet_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    table_id = int(cb.data.split(":")[1])
    table = await poker_service.get_table(session, table_id)
    if not table or table.status != "active":
        await cb.answer("❌ Раздача завершена.", show_alert=True)
        return

    players = await poker_service.get_players(session, table_id)
    actor = next((p for p in players if p.user_id == user.id), None)
    if not actor or actor.seat_index != table.current_seat or actor.status != "active":
        await cb.answer("❌ Сейчас не ваш ход.", show_alert=True)
        return

    max_total = actor.current_round_bet + actor.stack
    min_total = min(table.current_bet + max(table.last_raise_amount, table.big_blind), max_total)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"Мин. рейз ({fmt_num(min_total)})", callback_data=f"poker_raise:{table_id}:{min_total}"))
    if max_total > min_total:
        builder.row(InlineKeyboardButton(text=f"🔥 Ва-банк ({fmt_num(max_total)})", callback_data=f"poker_raise:{table_id}:{max_total}"))
    builder.row(InlineKeyboardButton(text="✏️ Своя сумма", callback_data=f"poker_raise_custom:{table_id}"))
    await safe_edit(cb.message, "💰 Выберите сумму рейза (итоговая ставка в этом круге):", reply_markup=builder.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("poker_raise:"))
async def cb_poker_raise(cb: CallbackQuery, session: AsyncSession, user: User):
    _, table_id_str, amount_str = cb.data.split(":")
    table_id = int(table_id_str)
    amount = int(amount_str)

    lock_key = cooldown_service.poker_action_lock_key(table_id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подождите...", show_alert=True)
        return

    table = await poker_service.get_table(session, table_id)
    if not table:
        await cb.answer("❌ Стол не найден.", show_alert=True)
        return

    result = await poker_service.apply_action(session, table, user.id, "raise", amount)
    if not result.get("ok"):
        await cb.answer(result["msg"], show_alert=True)
        return

    await safe_edit(cb.message, "✅ Рейз принят.", reply_markup=None)
    await notify_event(cb.bot, session, result)
    await cb.answer()


@router.callback_query(F.data.startswith("poker_raise_custom:"))
async def cb_poker_raise_custom(cb: CallbackQuery, state: FSMContext):
    table_id = int(cb.data.split(":")[1])
    await state.set_state(PokerRaiseFSM.waiting_amount)
    await state.update_data(table_id=table_id)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"poker_bet_menu:{table_id}"))
    await safe_edit(
        cb.message,
        "✏️ Введите итоговую сумму вашей ставки в этом круге торгов:",
        reply_markup=cancel_kb.as_markup(),
    )
    await cb.answer()


@router.message(PokerRaiseFSM.waiting_amount)
async def msg_poker_raise_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    table_id = data.get("table_id")
    await state.clear()
    if table_id is None:
        return

    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Введите целое число.", reply_markup=back_kb("poker_menu"), parse_mode="HTML")
        return

    lock_key = cooldown_service.poker_action_lock_key(table_id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await message.answer("⏳ Подождите...", reply_markup=back_kb("poker_menu"))
        return

    table = await poker_service.get_table(session, table_id)
    if not table:
        await message.answer("❌ Стол не найден.", reply_markup=back_kb("poker_menu"))
        return

    result = await poker_service.apply_action(session, table, user.id, "raise", amount)
    if not result.get("ok"):
        await message.answer(result["msg"], reply_markup=back_kb("poker_menu"), parse_mode="HTML")
        return

    await message.answer("✅ Рейз принят.")
    await notify_event(message.bot, session, result)
