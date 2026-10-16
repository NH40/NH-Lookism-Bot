"""PvP-покер (хендлеры): лобби, создание стола, вход, ходы, экран стола.

Экран стола у каждого игрока — ОДНО сообщение (`poker_players.message_id`), которое
перерисовывается после каждого хода любого игрока (`push_event`), итог раздачи — отдельным
сообщением. `push_event()` — публичная функция домена: её же зовёт фоновый проход
(`main.py`: старт столов и авто-ходы по таймауту).
"""
from __future__ import annotations

from bot.keyboards.common import back_menu

import json
import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.poker import POKER_ACTION_TIMEOUT_SECONDS, POKER_BUY_INS, POKER_WAIT_OPTIONS_SECONDS
from bot.constant.poker import (
    CB_POKER_ACT_PREFIX,
    CB_POKER_CREATE,
    CB_POKER_CREATE_PREFIX,
    CB_POKER_JOIN_PREFIX,
    CB_POKER_LEAVE_PREFIX,
    CB_POKER_OPEN,
    CB_POKER_VIEW_PREFIX,
    PLAYER_ACTIVE,
    PLAYER_ALL_IN,
    PLAYER_FOLDED,
    TABLE_ACTIVE,
    TABLE_WAITING,
)
from bot.db.models.gang import Gang
from bot.db.models.poker import PokerPlayer, PokerTable
from bot.keyboards.poker import buy_in_menu, lobby_menu, players_menu, table_menu, wait_menu
from bot.services.gang import get_gang
from bot.services.poker import (
    PokerError,
    PokerEvent,
    act,
    create,
    get_table,
    join,
    leave,
    lobby,
    min_raise_to,
    seat_of,
    to_call,
)
from bot.services.poker.engine import format_cards
from bot.texts.poker import (
    BOARD_NONE,
    CANCELLED,
    CREATE_BUY_IN,
    CREATE_PLAYERS,
    CREATE_WAIT,
    CREATED_ALERT,
    ERRORS,
    HAND_NAMES,
    JOINED_ALERT,
    LEAVING,
    LEFT,
    LOBBY_EMPTY,
    LOBBY_ROW,
    LOBBY_SCREEN,
    RESULT,
    RESULT_BOARD,
    RESULT_CLOSED,
    RESULT_LINE_FOLD_WIN,
    RESULT_LINE_SHOWDOWN,
    RESULT_WON,
    SEAT_ALL_IN,
    SEAT_BET,
    SEAT_DEALER,
    SEAT_FOLDED,
    SEAT_IDLE,
    SEAT_LEAVING,
    SEAT_LINE,
    SEAT_TURN,
    STREET_NAMES,
    TABLE_ACTIVE as TABLE_ACTIVE_TEXT,
    TABLE_CLOSED,
    TABLE_WAITING as TABLE_WAITING_TEXT,
    TURN_OTHER,
    TURN_YOURS,
    TURN_YOURS_CHECK,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.formatting import esc, format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

log = logging.getLogger(__name__)
router = Router(name="poker")

_BOARD_SIZE = {"preflop": 0, "flop": 3, "turn": 4, "river": 5, "showdown": 5}


async def _names(session: AsyncSession, user_ids: list[int]) -> dict[int, str]:
    rows = await session.execute(select(Gang.user_id, Gang.name).where(Gang.user_id.in_(user_ids)))
    names = {uid: esc(name) for uid, name in rows.all()}
    return {uid: names.get(uid, "—") for uid in user_ids}


async def render_lobby(session: AsyncSession, user_id: int):
    tables = await lobby(session)
    rows = "".join(
        LOBBY_ROW.format(id=t.id, buy_in=format_number(t.buy_in), players=t.players, max=t.max_players, countdown=format_countdown(t.starts_in))
        for t in tables
    ) or LOBBY_EMPTY
    return LOBBY_SCREEN.format(timeout=POKER_ACTION_TIMEOUT_SECONDS, tables=rows), lobby_menu(tables, await seat_of(session, user_id))


def _view(table: PokerTable, players: list[PokerPlayer], names: dict[int, str], user_id: int):
    """Экран стола глазами игрока `user_id` — (текст, клавиатура)."""
    me = next((p for p in players if p.user_id == user_id), None)
    if table.status == TABLE_WAITING:
        seats = "\n".join(f"{SEAT_IDLE}{names[p.user_id]}" for p in players)
        left = max(0, int((table.starts_at - datetime.now(timezone.utc)).total_seconds()))
        text = TABLE_WAITING_TEXT.format(
            id=table.id, buy_in=format_number(table.buy_in), sb=format_number(table.small_blind), bb=format_number(table.big_blind),
            players=len(players), max=table.max_players, seats=seats, countdown=format_countdown(left),
        )
        return text, table_menu(table.id, table.hand_no, my_turn=False, call=0, min_raise=0, pot_raise=0, all_in=0, can_raise=False)
    if table.status != TABLE_ACTIVE or me is None:
        return TABLE_CLOSED.format(id=table.id), table_menu(table.id, 0, my_turn=False, call=0, min_raise=0, pot_raise=0, all_in=0, can_raise=False, closed=True)
    board = json.loads(table.community)[:_BOARD_SIZE.get(table.street, 0)]
    dealer = table.dealer_seat % len(players)
    lines = []
    for p in players:
        status = SEAT_FOLDED if p.status == PLAYER_FOLDED else SEAT_ALL_IN if p.status == PLAYER_ALL_IN else ""
        lines.append(SEAT_LINE.format(
            marker=SEAT_TURN if p.seat == table.current_seat else SEAT_IDLE,
            name=names[p.user_id] + (SEAT_DEALER if p.seat == dealer else ""),
            stack=format_number(p.stack), bet=SEAT_BET.format(bet=format_number(p.round_bet)) if p.round_bet else "",
            status=status + (SEAT_LEAVING if p.leaving else ""),
        ))
    my_turn = me.seat == table.current_seat and me.status == PLAYER_ACTIVE
    call = to_call(table, me)
    seconds = max(0, int((table.action_deadline - datetime.now(timezone.utc)).total_seconds())) if table.action_deadline else 0
    if my_turn:
        turn = (TURN_YOURS if call else TURN_YOURS_CHECK).format(seconds=seconds, call=format_number(call))
    else:
        current = next((p for p in players if p.seat == table.current_seat), None)
        turn = TURN_OTHER.format(name=names[current.user_id]) if current else ""
    text = TABLE_ACTIVE_TEXT.format(
        id=table.id, hand=table.hand_no, street=STREET_NAMES.get(table.street, table.street),
        board=format_cards(board) if board else BOARD_NONE, pot=format_number(table.pot),
        sb=format_number(table.small_blind), bb=format_number(table.big_blind), seats="\n".join(lines),
        hole=format_cards(json.loads(me.hole)), turn=turn,
    )
    all_in = me.round_bet + me.stack
    min_raise = min_raise_to(table, me)
    pot_raise = min(all_in, table.current_bet + table.pot + call)
    return text, table_menu(
        table.id, table.hand_no, my_turn=my_turn, call=min(call, me.stack), min_raise=min_raise, pot_raise=pot_raise,
        all_in=all_in, can_raise=all_in > table.current_bet,
    )


def _result_text(result: dict, names: dict[int, str]) -> str:
    board = RESULT_BOARD.format(board=format_cards(result["board"])) if result["board"] else ""
    lines = ""
    for p in result["players"]:
        won = RESULT_WON.format(amount=format_number(p["won"])) if p["won"] else ""
        if result["showdown"]:
            if p["hole"]:
                lines += RESULT_LINE_SHOWDOWN.format(name=names.get(p["user_id"], "—"), hole=format_cards(p["hole"]), hand=HAND_NAMES[p["hand"][0]], won=won)
        elif p["won"]:
            lines += RESULT_LINE_FOLD_WIN.format(name=names.get(p["user_id"], "—"), won=won)
    text = RESULT.format(hand=result["hand_no"], pot=format_number(result["pot"]), board=board, lines=lines)
    return text + (RESULT_CLOSED if result.get("closed") else "")


async def _send_view(bot: Bot, session: AsyncSession, table: PokerTable, players: list[PokerPlayer], names: dict[int, str], player: PokerPlayer) -> None:
    text, markup = _view(table, players, names, player.user_id)
    if player.message_id:
        try:
            await bot.edit_message_text(text, chat_id=player.user_id, message_id=player.message_id, reply_markup=markup)
            return
        except TelegramAPIError as exc:
            if "not modified" in str(exc):
                return
    try:
        sent = await bot.send_message(player.user_id, text, reply_markup=markup)
    except TelegramAPIError:
        return
    await session.execute(update(PokerPlayer).where(PokerPlayer.id == player.id).values(message_id=sent.message_id))
    await session.commit()


async def push_event(bot: Bot, session_factory: async_sessionmaker[AsyncSession], event: PokerEvent, skip_user: int | None = None) -> None:
    """Показать событие всем за столом: итог раздачи (если был) и свежий экран стола. Доставка
    best-effort — игрок мог заблокировать бота, стол живёт дальше."""
    async with session_factory() as session:
        table, players = await get_table(session, event.table_id)
        if table is None:
            return
        names = await _names(session, list({*event.user_ids, *(p.user_id for p in players)}))
        seated = {p.user_id for p in players}
        for user_id in event.user_ids:
            try:
                if event.kind == "hand_finished" and event.result:
                    await bot.send_message(user_id, _result_text(event.result, names))
                elif event.kind == "cancelled":
                    await bot.send_message(user_id, CANCELLED.format(id=table.id))
                elif event.kind == "hand_finished" and user_id not in seated:
                    await bot.send_message(user_id, TABLE_CLOSED.format(id=table.id))
            except TelegramAPIError:
                pass
        for player in players:
            if player.user_id == skip_user:
                continue
            try:
                await _send_view(bot, session, table, players, names, player)
            except Exception:
                log.exception("poker view push failed")


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


@router.callback_query(F.data == CB_POKER_OPEN)
async def cb_poker_open(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    text, markup = await render_lobby(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_POKER_CREATE)
async def cb_poker_create(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    await safe_edit_text(callback.message, CREATE_BUY_IN, reply_markup=buy_in_menu())


@router.callback_query(F.data.startswith(CB_POKER_CREATE_PREFIX))
async def cb_poker_create_step(callback: CallbackQuery, session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]) -> None:
    parts = callback.data.removeprefix(CB_POKER_CREATE_PREFIX).split(":")
    if not all(p.isdigit() for p in parts) or int(parts[0]) not in POKER_BUY_INS or not await _guard(callback, session):
        await callback.answer()
        return
    buy_in = int(parts[0])
    if len(parts) == 1:
        await callback.answer()
        await safe_edit_text(callback.message, CREATE_PLAYERS.format(buy_in=format_number(buy_in)), reply_markup=players_menu(buy_in))
        return
    players = int(parts[1])
    if len(parts) == 2:
        await callback.answer()
        await safe_edit_text(callback.message, CREATE_WAIT.format(buy_in=format_number(buy_in), players=players), reply_markup=wait_menu(buy_in, players))
        return
    wait = int(parts[2])
    if wait not in POKER_WAIT_OPTIONS_SECONDS:
        await callback.answer()
        return
    try:
        event = await create(session, callback.from_user.id, buy_in, players, wait)
    except PokerError as exc:
        await callback.answer(ERRORS[exc.code], show_alert=True)
        return
    await callback.answer(CREATED_ALERT)
    await _show_table_here(callback, session_factory, event.table_id)


async def _show_table_here(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession], table_id: int) -> None:
    """Текущее сообщение становится «экраном стола» игрока."""
    async with session_factory() as session:
        table, players = await get_table(session, table_id)
        me = next((p for p in players if p.user_id == callback.from_user.id), None)
        if table is None:
            return
        names = await _names(session, [p.user_id for p in players])
        text, markup = _view(table, players, names, callback.from_user.id)
        await safe_edit_text(callback.message, text, reply_markup=markup)
        if me is not None and me.message_id != callback.message.message_id:
            await session.execute(update(PokerPlayer).where(PokerPlayer.id == me.id).values(message_id=callback.message.message_id))
            await session.commit()


@router.callback_query(F.data.startswith(CB_POKER_JOIN_PREFIX))
async def cb_poker_join(callback: CallbackQuery, session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]) -> None:
    raw = callback.data.removeprefix(CB_POKER_JOIN_PREFIX)
    if not raw.isdigit() or not await _guard(callback, session):
        await callback.answer()
        return
    try:
        event = await join(session, callback.from_user.id, int(raw))
    except PokerError as exc:
        await callback.answer(ERRORS[exc.code], show_alert=True)
        return
    await callback.answer(JOINED_ALERT)
    await _show_table_here(callback, session_factory, event.table_id)
    await push_event(callback.bot, session_factory, event, skip_user=callback.from_user.id)


@router.callback_query(F.data.startswith(CB_POKER_VIEW_PREFIX))
async def cb_poker_view(callback: CallbackQuery, session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]) -> None:
    raw = callback.data.removeprefix(CB_POKER_VIEW_PREFIX)
    if not raw.isdigit() or not await _guard(callback, session):
        await callback.answer()
        return
    await callback.answer()
    await _show_table_here(callback, session_factory, int(raw))


@router.callback_query(F.data.startswith(CB_POKER_LEAVE_PREFIX))
async def cb_poker_leave(callback: CallbackQuery, session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]) -> None:
    raw = callback.data.removeprefix(CB_POKER_LEAVE_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    try:
        event = await leave(session, callback.from_user.id, int(raw))
    except PokerError as exc:
        await callback.answer(ERRORS[exc.code], show_alert=True)
        return
    await callback.answer()
    if event.kind == "left":
        await callback.message.answer(LEFT.format(id=event.table_id), reply_markup=back_menu(CB_POKER_OPEN))
        await push_event(callback.bot, session_factory, PokerEvent(event.table_id, "joined", []))
    else:
        await callback.message.answer(LEAVING, reply_markup=back_menu(CB_POKER_OPEN))
        await push_event(callback.bot, session_factory, PokerEvent(event.table_id, "action", []))


@router.callback_query(F.data.startswith(CB_POKER_ACT_PREFIX))
async def cb_poker_act(callback: CallbackQuery, session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]) -> None:
    parts = callback.data.removeprefix(CB_POKER_ACT_PREFIX).split(":")
    if len(parts) != 4 or not (parts[0].isdigit() and parts[1].isdigit() and parts[3].isdigit()):
        await callback.answer()
        return
    table_id, hand_no, action, amount = int(parts[0]), int(parts[1]), parts[2], int(parts[3])
    # Popup-тексты — без HTML.
    try:
        event = await act(session, callback.from_user.id, table_id, hand_no, action, amount)
    except PokerError as exc:
        await callback.answer(ERRORS[exc.code], show_alert=True)
        return
    await callback.answer()
    await push_event(callback.bot, session_factory, event)

