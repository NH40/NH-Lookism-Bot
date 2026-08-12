"""Блэкджек против дилера-бота."""
import json
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.bank.casino.blackjack_service import (
    blackjack_service, format_hand, hand_value, is_natural
)
from app.services.bank.casino.common import CASINO_RESOURCES
from app.services.bank.casino.squad_service import squad_casino_service
from app.services.cooldown_service import cooldown_service
from app.utils.formatters import fmt_num
from app.utils.keyboards.common import back_kb
from app.utils.menu_media import safe_edit

logger = logging.getLogger(__name__)
router = Router()


class BlackjackFSM(StatesGroup):
    waiting_bet = State()
    playing = State()


# ── Клавиатуры ──────────────────────────────────────────────────────────────

def _bj_main_kb():
    builder = InlineKeyboardBuilder()
    for res, label in CASINO_RESOURCES.items():
        builder.row(InlineKeyboardButton(
            text=label,
            callback_data=f"bj_pick:{res}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_casino"))
    return builder.as_markup()


def _play_kb(hand: dict | None = None):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🃏 Взять", callback_data="bj_hit"),
        InlineKeyboardButton(text="✋ Стоп, мне не приятно", callback_data="bj_stand"),
    )
    can_double = hand is None or (len(hand.get("player_cards", [])) == 2 and not hand.get("doubled"))
    if can_double:
        builder.row(InlineKeyboardButton(text="💎 Удвоить", callback_data="bj_double"))
    return builder.as_markup()


def _finish_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Играть снова", callback_data="bank_casino_blackjack"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_casino"))
    return builder.as_markup()


# ── Вспомогательные ──────────────────────────────────────────────────────────

def _render_playing(hand: dict) -> str:
    player_cards = hand["player_cards"]
    dealer_cards = hand["dealer_cards"]
    player_value = hand_value(player_cards)

    lines = [
        "🃏 <b>Блэкджек</b>\n",
        f"Дилер: {format_hand([dealer_cards[0]])} + ?",
        f"Ваши карты: {format_hand(player_cards)}",
        f"Сумма: <b>{player_value}</b>\n",
        f"Ставка: {fmt_num(hand['bet'])} {CASINO_RESOURCES.get(hand['resource'], hand['resource'])}",
    ]
    if hand.get("rank"):
        lines.append(f"Ранг: {hand['rank']}")
    return "\n".join(lines)


def _render_finished(hand: dict, outcome: str) -> str:
    player_cards = hand["player_cards"]
    dealer_cards = hand["dealer_cards"]
    player_value = hand_value(player_cards)
    dealer_value = hand_value(dealer_cards)

    outcome_map = {
        "blackjack": "🎉 БЛЭКДЖЕК! ВЫИГРЫШ!",
        "win": "🎉 ВЫИГРЫШ!",
        "loss": "💔 ПРОИГРЫШ.",
        "push": "🔄 НИЧЬЯ.",
        "bust": "💔 ПЕРЕБОР.",
        "push_natural": "🔄 У обоих блэкджек — ничья.",
    }

    lines = [
        "🃏 <b>Блэкджек — результат</b>\n",
        f"Дилер: {format_hand(dealer_cards)} = {dealer_value}",
        f"Ваши карты: {format_hand(player_cards)} = {player_value}\n",
        outcome_map.get(outcome, outcome),
    ]

    if hand.get("resource") == "squad":
        total_stake = hand.get("total_stake", 0)
        payout = hand.get("payout", 0)
        bonus = hand.get("bonus", 0)
        
        if outcome in ("win", "blackjack"):
            lines.append(f"✅ Выигрыш: +{fmt_num(payout)} статистов")
            if bonus:
                lines.append(f"🎁 Бонус: +{fmt_num(bonus)} статистов")
        elif outcome == "push":
            lines.append(f"🔄 Возврат: {fmt_num(payout)} статистов")
        else:
            lines.append(f"❌ Потеряно: {fmt_num(total_stake)} статистов")
    else:
        if outcome in ("win", "blackjack"):
            lines.append(f"✅ Выигрыш: {fmt_num(hand.get('payout', 0))} {CASINO_RESOURCES.get(hand['resource'], hand['resource'])}")
        elif outcome == "push":
            lines.append(f"🔄 Возврат: {fmt_num(hand.get('payout', 0))} {CASINO_RESOURCES.get(hand['resource'], hand['resource'])}")
        else:
            lines.append(f"❌ Потеряно: {fmt_num(hand.get('total_stake', 0))} {CASINO_RESOURCES.get(hand['resource'], hand['resource'])}")

    return "\n".join(lines)


# ── Главное меню ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "bank_casino_blackjack")
async def cb_bj_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(cb, "🃏 <b>Блэкджек</b>\n\nВыберите ресурс для ставки:", _bj_main_kb())
    await cb.answer()


@router.callback_query(F.data == "bj_menu")
async def cb_bj_menu_back(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(cb, "🃏 <b>Блэкджек</b>\n\nВыберите ресурс для ставки:", _bj_main_kb())
    await cb.answer()


# ── Выбор ресурса ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("bj_pick:"))
async def cb_bj_pick(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    resource = cb.data.split(":")[1]

    if resource not in CASINO_RESOURCES:
        await cb.answer("❌ Неизвестный ресурс.", show_alert=True)
        return

    if resource == "squad":
        rank_counts = await squad_casino_service.get_rank_counts(session, user.id)
        available_ranks = await squad_casino_service.get_available_ranks(session, user.id)

        if not available_ranks:
            await cb.answer("❌ Нет доступных рангов (нужно минимум 5 статистов).", show_alert=True)
            return

        builder = InlineKeyboardBuilder()
        for rank in available_ranks:
            count = rank_counts.get(rank, 0)
            builder.row(InlineKeyboardButton(
                text=f"👥 {rank} — {fmt_num(count)} шт.",
                callback_data=f"bj_squad_rank:{rank}"
            ))
        builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="bj_menu"))

        await safe_edit(
            cb,
            "👥 <b>Выберите ранг статистов</b>\n\n"
            f"Минимальный депозит: {squad_casino_service.MIN_DEPOSIT} статистов\n"
            "При выигрыше: возврат + 20% (x1.2)\n\n"
            "<i>Выберите ранг для депозита:</i>",
            builder.as_markup()
        )
        await cb.answer()
        return

    balance = getattr(user, resource, 0)
    await state.set_state(BlackjackFSM.waiting_bet)
    await state.update_data(resource=resource)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bj_menu"))

    await safe_edit(
        cb,
        f"🃏 <b>Блэкджек — {CASINO_RESOURCES[resource]}</b>\n\n"
        f"Баланс: {fmt_num(balance)}\n\n"
        f"Введите сумму ставки:",
        builder.as_markup()
    )
    await cb.answer()


# ── Выбор ранга для статистов ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("bj_squad_rank:"))
async def cb_bj_squad_rank(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    rank = cb.data.split(":")[1]
    await state.set_state(BlackjackFSM.waiting_bet)
    await state.update_data(resource="squad", rank=rank)

    rank_counts = await squad_casino_service.get_rank_counts(session, user.id)
    count = rank_counts.get(rank, 0)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bj_menu"))

    await safe_edit(
        cb,
        f"👥 <b>Статисты ранга {rank}</b>\n\n"
        f"Доступно: {fmt_num(count)} статистов\n"
        f"Минимальный депозит: {squad_casino_service.MIN_DEPOSIT} статистов\n"
        f"Множитель выигрыша: x1.2\n\n"
        f"Введите количество статистов для депозита:",
        builder.as_markup()
    )
    await cb.answer()


# ── Ввод суммы ставки ────────────────────────────────────────────────────────

@router.message(BlackjackFSM.waiting_bet)
async def msg_bj_bet(message: Message, session: AsyncSession, user: User, state: FSMContext):
    try:
        data = await state.get_data()
        resource = data.get("resource")
        rank = data.get("rank")
        await state.clear()

        if not resource:
            await message.answer("❌ Ресурс не выбран.", reply_markup=back_kb("bj_menu"), parse_mode="HTML")
            return

        try:
            amount = int(message.text.strip().replace(" ", "").replace(",", ""))
        except ValueError:
            await message.answer("❌ Введите целое число.", reply_markup=back_kb("bj_menu"), parse_mode="HTML")
            return

        if amount <= 0:
            await message.answer("❌ Ставка должна быть больше нуля.", reply_markup=back_kb("bj_menu"), parse_mode="HTML")
            return

        if resource == "squad" and amount < squad_casino_service.MIN_DEPOSIT:
            await message.answer(
                f"❌ Минимальный депозит: {squad_casino_service.MIN_DEPOSIT} статистов.",
                reply_markup=back_kb("bj_menu"),
                parse_mode="HTML"
            )
            return

        lock_key = cooldown_service.blackjack_lock_key(user.id)
        if not await cooldown_service.acquire_lock(lock_key, ttl=5):
            await message.answer("⏳ Подождите, предыдущее действие ещё обрабатывается.", reply_markup=back_kb("bj_menu"))
            return
        try:
            result = await blackjack_service.start(session, user, resource, amount, rank)
        finally:
            await cooldown_service.release_lock(lock_key)
        logger.info(f"Blackjack start result: {result}")

        if not result.get("ok", False):
            if result.get("x3_warn"):
                await message.answer(result["msg"], reply_markup=back_kb("bj_menu"), parse_mode="HTML")
            else:
                await message.answer(result.get("msg", "❌ Ошибка."), reply_markup=back_kb("bj_menu"), parse_mode="HTML")
            return

        hand = result["hand"]

        if result.get("finished"):
            await state.clear()
            text = _render_finished(hand, result.get("outcome", "loss"))
            kb = _finish_kb()
            await message.answer(text, reply_markup=kb, parse_mode="HTML")
            return

        await state.set_state(BlackjackFSM.playing)
        await state.update_data(hand=hand)

        text = _render_playing(hand)
        kb = _play_kb(hand)
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Blackjack bet error: {e}", exc_info=True)
        await state.clear()
        await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=back_kb("bj_menu"), parse_mode="HTML")


# ── Игровые действия ─────────────────────────────────────────────────────────

async def _run_bj_action(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext, action_name: str, action_fn):
    """Общий обработчик hit/stand/double: лок, чтение раздачи из FSM, вызов
    сервисного метода, отрисовка результата. Отличается только action_fn."""
    lock_key = cooldown_service.blackjack_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подождите...", show_alert=True)
        return
    try:
        data = await state.get_data()
        hand = data.get("hand")
        if not hand:
            await cb.answer("❌ Игра не найдена. Начните заново.", show_alert=True)
            await state.clear()
            return

        result = await action_fn(session, user, hand)
        logger.info(f"Blackjack {action_name} result: {result}")

        if not result.get("ok", True):
            await cb.answer(result.get("msg", "❌ Ошибка."), show_alert=True)
            return

        if result.get("finished"):
            await state.clear()
            text = _render_finished(result["hand"], result.get("outcome", "loss"))
            kb = _finish_kb()
        else:
            await state.update_data(hand=result["hand"])
            text = _render_playing(result["hand"])
            kb = _play_kb(result["hand"])

        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
        await cb.answer()
    except Exception as e:
        logger.error(f"Blackjack {action_name} error: {e}", exc_info=True)
        await state.clear()
        await cb.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    finally:
        await cooldown_service.release_lock(lock_key)


@router.callback_query(F.data == "bj_hit", BlackjackFSM.playing)
async def cb_bj_hit(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    await _run_bj_action(cb, session, user, state, "hit", blackjack_service.hit)


@router.callback_query(F.data == "bj_stand", BlackjackFSM.playing)
async def cb_bj_stand(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    await _run_bj_action(cb, session, user, state, "stand", blackjack_service.stand)


@router.callback_query(F.data == "bj_double", BlackjackFSM.playing)
async def cb_bj_double(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    await _run_bj_action(cb, session, user, state, "double", blackjack_service.double)