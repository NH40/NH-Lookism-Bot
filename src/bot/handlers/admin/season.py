"""Админка — Сезон пасса и задания (хендлеры)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, SECTION_SEASON
from bot.constant.admin import season_admin as C
from bot.handlers.admin.common import guard, parse_id
from bot.keyboards.admin import season_admin as K
from bot.services.admin import players as players_svc
from bot.services.admin import roles
from bot.services.admin import season_admin as svc
from bot.states.admin_season import AdminSeasonStates
from bot.texts.admin import season_admin as T
from bot.texts.quest import TASK_EMOJI
from bot.utils.formatting import esc, format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_season")


def _label(user) -> str:
    return f"@{user.username}" if user.username else f"id{user.id}"


async def _player_label(session: AsyncSession, uid: int) -> str | None:
    user = await players_svc.find(session, str(uid))
    return _label(user) if user else None


async def _card_screen(session: AsyncSession, uid: int) -> tuple[str, InlineKeyboardMarkup] | None:
    label = await _player_label(session, uid)
    if label is None:
        return None
    info = await svc.pass_info(session, uid)
    text = T.PLAYER_CARD.format(
        player=esc(label), number=info.season.number, level=info.level, xp=format_number(info.xp),
        premium=T.YES if info.premium else T.NO, free=info.claimed_free, paid=info.claimed_premium,
    )
    return text, K.player_card(uid)


async def _show_card(callback: CallbackQuery, session: AsyncSession, uid: int) -> None:
    screen = await _card_screen(session, uid)
    if screen is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, screen[0], reply_markup=screen[1])


async def _quests_screen(session: AsyncSession, uid: int) -> tuple[str, InlineKeyboardMarkup] | None:
    label = await _player_label(session, uid)
    if label is None:
        return None
    status = await svc.quest_status(session, uid)
    lines = [
        T.QUEST_LINE.format(
            status=T.STATUS_DONE if q.done else T.STATUS_TODO, emoji=TASK_EMOJI.get(q.task, "❔"), task=esc(q.task),
            progress=format_number(q.progress), target=format_number(q.target), xp=q.xp,
        )
        for q in status.quests
    ]
    text = T.QUESTS_HEAD.format(player=esc(label)) + "\n".join(f"#{q.slot} {line}" for q, line in zip(status.quests, lines)) + T.QUESTS_HINT
    return text, K.quests(uid, [q.slot for q in status.quests if not q.done])


@router.callback_query(F.data == f"{CB_ADMIN_SECTION_PREFIX}{SECTION_SEASON}")
async def cb_section(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_SEASON):
        return
    await state.clear()
    info = await svc.season_info(session)
    await callback.answer()
    await safe_edit_text(
        callback.message,
        T.MENU.format(
            number=info.season.number, ends=info.season.ends_at.strftime("%d.%m.%Y %H:%M UTC"),
            left=format_countdown(info.left_seconds), premium=info.premium,
        ),
        reply_markup=K.menu(),
    )


@router.callback_query(F.data == C.CB_SE_NEW_ASK)
async def cb_new_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_SEASON):
        return
    info = await svc.season_info(session)
    await callback.answer()
    await safe_edit_text(
        callback.message, T.CONFIRM_NEW.format(number=info.season.number, next=info.season.number + 1),
        reply_markup=K.confirm_new(),
    )


@router.callback_query(F.data == C.CB_SE_NEW_OK)
async def cb_new_ok(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_SEASON):
        return
    number = await svc.start_new_season(session, callback.from_user.id)
    await callback.answer(T.DONE_NEW.format(number=number), show_alert=True)
    await safe_edit_text(callback.message, T.DONE_NEW.format(number=number), reply_markup=K.back_to_section())


# --- игрок ---

@router.callback_query(F.data == C.CB_SE_PLAYER)
async def cb_player(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_SEASON):
        return
    await state.set_state(AdminSeasonStates.waiting_player)
    await callback.answer()
    await safe_edit_text(callback.message, T.ASK_PLAYER, reply_markup=K.back_to_section())


@router.message(StateFilter(AdminSeasonStates.waiting_player), F.text)
async def msg_player(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_SEASON):
        return
    user = await players_svc.find(session, message.text)
    if user is None:
        await message.answer(T.PLAYER_NOT_FOUND, reply_markup=K.back_to_section())
        return
    await state.clear()
    screen = await _card_screen(session, user.id)
    await message.answer(screen[0], reply_markup=screen[1])


@router.callback_query(F.data.startswith(C.CB_SE_CARD_PREFIX))
async def cb_card(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_SEASON):
        return
    uid = parse_id(callback.data, C.CB_SE_CARD_PREFIX)
    if uid is None:
        return
    await state.clear()
    await _show_card(callback, session, uid)


@router.callback_query(F.data.startswith(C.CB_SE_XP_PREFIX))
async def cb_xp(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_SEASON):
        return
    uid = parse_id(callback.data, C.CB_SE_XP_PREFIX)
    label = await _player_label(session, uid) if uid is not None else None
    if label is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    info = await svc.pass_info(session, uid)
    await state.set_state(AdminSeasonStates.waiting_xp)
    await state.update_data({C.FSM_USER_ID: uid})
    await callback.answer()
    await safe_edit_text(callback.message, T.ASK_XP.format(player=esc(label), xp=format_number(info.xp)), reply_markup=K.to_player(uid))


@router.message(StateFilter(AdminSeasonStates.waiting_xp), F.text)
async def msg_xp(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_SEASON):
        return
    uid = (await state.get_data())[C.FSM_USER_ID]
    raw = message.text.strip().replace(" ", "")
    if not raw.lstrip("+-").isdigit():
        await message.answer(T.BAD_NUMBER, reply_markup=K.to_player(uid))
        return
    new_xp = await svc.give_xp(session, message.from_user.id, uid, int(raw))
    if new_xp is None:
        await message.answer(T.OUT_OF_RANGE.format(max=format_number(C.XP_LIMIT)), reply_markup=K.to_player(uid))
        return
    await state.clear()
    await message.answer(T.DONE_XP.format(delta=f"{int(raw):+d}", xp=format_number(new_xp)), reply_markup=K.to_player(uid))


@router.callback_query(F.data.startswith(C.CB_SE_PREMIUM_PREFIX))
async def cb_premium(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_SEASON):
        return
    uid = parse_id(callback.data, C.CB_SE_PREMIUM_PREFIX)
    if uid is None or await _player_label(session, uid) is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    on = await svc.toggle_premium(session, callback.from_user.id, uid)
    await callback.answer(T.DONE_PREMIUM_ON if on else T.DONE_PREMIUM_OFF, show_alert=True)
    await _show_card(callback, session, uid)


@router.callback_query(F.data.startswith(C.CB_SE_RESET_ASK_PREFIX))
async def cb_reset_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_SEASON):
        return
    uid = parse_id(callback.data, C.CB_SE_RESET_ASK_PREFIX)
    label = await _player_label(session, uid) if uid is not None else None
    if label is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, T.CONFIRM_RESET.format(player=esc(label)), reply_markup=K.confirm_reset(uid))


@router.callback_query(F.data.startswith(C.CB_SE_RESET_OK_PREFIX))
async def cb_reset_ok(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_SEASON):
        return
    uid = parse_id(callback.data, C.CB_SE_RESET_OK_PREFIX)
    if uid is None or await _player_label(session, uid) is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await svc.reset_claims(session, callback.from_user.id, uid)
    await callback.answer(T.DONE_RESET, show_alert=True)
    await _show_card(callback, session, uid)


# --- задания ---

async def _show_quests(callback: CallbackQuery, session: AsyncSession, uid: int) -> None:
    screen = await _quests_screen(session, uid)
    if screen is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, screen[0], reply_markup=screen[1])


@router.callback_query(F.data.startswith(C.CB_SE_QUESTS_PREFIX))
async def cb_quests(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_SEASON):
        return
    uid = parse_id(callback.data, C.CB_SE_QUESTS_PREFIX)
    if uid is None:
        return
    await _show_quests(callback, session, uid)


@router.callback_query(F.data.startswith(C.CB_SE_QUEST_DONE_PREFIX))
async def cb_quest_done(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_SEASON):
        return
    parts = callback.data.removeprefix(C.CB_SE_QUEST_DONE_PREFIX).split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    uid, slot = int(parts[0]), int(parts[1])
    ok = await svc.complete_quest(session, callback.from_user.id, uid, slot)
    await callback.answer(T.DONE_QUEST if ok else T.ALERT_QUEST_DONE, show_alert=True)
    await _show_quests(callback, session, uid)


@router.callback_query(F.data.startswith(C.CB_SE_QUEST_REROLL_ASK_PREFIX))
async def cb_reroll_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_SEASON):
        return
    uid = parse_id(callback.data, C.CB_SE_QUEST_REROLL_ASK_PREFIX)
    label = await _player_label(session, uid) if uid is not None else None
    if label is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, T.CONFIRM_REROLL.format(player=esc(label)), reply_markup=K.confirm_reroll(uid))


@router.callback_query(F.data.startswith(C.CB_SE_QUEST_REROLL_OK_PREFIX))
async def cb_reroll_ok(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_SEASON):
        return
    uid = parse_id(callback.data, C.CB_SE_QUEST_REROLL_OK_PREFIX)
    if uid is None or await _player_label(session, uid) is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await svc.reroll_set(session, callback.from_user.id, uid)
    await callback.answer(T.DONE_REROLL, show_alert=True)
    await _show_quests(callback, session, uid)
