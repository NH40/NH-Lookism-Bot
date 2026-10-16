"""Админка — Наказания и сброс (из карточки игрока): бан со сроком и причиной, разбан, сброс
кулдаунов, сброс прогресса и удаление аккаунта (последние два — с подтверждением)."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin import CB_ADMIN_PLAYER_PUNISH_PREFIX, SECTION_PUNISH
from bot.constant.admin.players_admin import (
    AUDIT_BAN,
    AUDIT_CLEAR_COOLDOWNS,
    AUDIT_DELETE_ACCOUNT,
    AUDIT_RESET_PLAYER,
    AUDIT_UNBAN,
    BAN_DURATIONS,
    BAN_REASON_MAX_LEN,
    CB_PUNISH_BAN,
    CB_PUNISH_BAN_DURATION,
    CB_PUNISH_BAN_NO_REASON,
    CB_PUNISH_COOLDOWNS,
    CB_PUNISH_DELETE_ASK,
    CB_PUNISH_DELETE_YES,
    CB_PUNISH_MENU,
    CB_PUNISH_RESET_ASK,
    CB_PUNISH_RESET_YES,
    CB_PUNISH_UNBAN,
)
from bot.db.models.user import User
from bot.handlers.admin.common import guard
from bot.handlers.admin.player_target import back_to_card, edit_screen, load_target, name_of, parse_args, reply_card
from bot.keyboards.admin import back_to_panel
from bot.keyboards.admin import players_admin as kb
from bot.services.admin import audit, players, players_admin, roles
from bot.states.admin_players import AdminPunishStates
from bot.texts.admin import players_admin as t
from bot.utils.formatting import esc

router = Router(name="admin_punish")


async def _open(
    callback: CallbackQuery, session: AsyncSession, prefix: str, *, protect: bool = False
) -> tuple[list[str], User] | None:
    """Права + разбор `callback_data` + цель. `protect` — запретить действие над собой и над
    сотрудниками админки. None — ответ уже дан."""
    if not await guard(callback, session, SECTION_PUNISH):
        return None
    parsed = parse_args(callback.data, prefix)
    user = await load_target(callback, session, parsed[1] if parsed else None)
    if user is None:
        return None
    if protect and user.id == callback.from_user.id:
        await callback.answer(t.TARGET_IS_SELF_ALERT, show_alert=True)
        return None
    if protect and await roles.role_of(session, user.id) is not None:
        await callback.answer(t.TARGET_IS_STAFF_ALERT, show_alert=True)
        return None
    return parsed[0], user


async def _notify(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text)
    except TelegramAPIError:
        pass


# ------------------------------------ меню ------------------------------------

@router.callback_query(F.data.startswith(CB_ADMIN_PLAYER_PUNISH_PREFIX) | F.data.startswith(CB_PUNISH_MENU))
async def cb_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    prefix = CB_PUNISH_MENU if callback.data.startswith(CB_PUNISH_MENU) else CB_ADMIN_PLAYER_PUNISH_PREFIX
    opened = await _open(callback, session, prefix)
    if opened is None:
        return
    await state.clear()
    user = opened[1]
    banned = players.is_banned(user)
    until = ""
    if banned and not user.is_banned and user.banned_until:
        until = f" до {user.banned_until.strftime('%d.%m.%Y %H:%M UTC')}"
    status = t.STATUS_BANNED.format(until=until) if banned else t.STATUS_OK
    await edit_screen(callback, t.PUNISH_MENU.format(name=name_of(user), status=status), kb.punish_menu(user.id, banned))


# ------------------------------------- бан -------------------------------------

@router.callback_query(F.data.startswith(CB_PUNISH_BAN))
async def cb_ban(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_PUNISH_BAN, protect=True)
    if opened is None:
        return
    await state.clear()
    await edit_screen(callback, t.BAN_CHOOSE.format(name=name_of(opened[1])), kb.ban_durations(opened[1].id))


@router.callback_query(F.data.startswith(CB_PUNISH_BAN_DURATION))
async def cb_ban_duration(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_PUNISH_BAN_DURATION, protect=True)
    if opened is None or len(opened[0]) != 1 or opened[0][0] not in BAN_DURATIONS:
        return
    key, user = opened[0][0], opened[1]
    await state.set_state(AdminPunishStates.waiting_reason)
    await state.update_data(uid=user.id, key=key)
    text = t.BAN_REASON_PROMPT.format(name=name_of(user), duration=t.BAN_DURATION_TITLES[key], max=BAN_REASON_MAX_LEN)
    await edit_screen(callback, text, kb.ban_reason(user.id, key))


async def _apply_ban(session: AsyncSession, bot: Bot, admin_id: int, uid: int, key: str, reason: str | None) -> str:
    """Бан + аудит + commit + уведомление игроку. → подпись срока."""
    until = await players_admin.ban(session, uid, BAN_DURATIONS[key], reason)
    await audit.log(session, admin_id, AUDIT_BAN, uid, {"duration": key, "reason": reason})
    await session.commit()
    duration = t.BAN_DURATION_TITLES[key] if until is None else f"до {until.strftime('%d.%m.%Y %H:%M UTC')}"
    reason_line = t.PLAYER_BANNED_REASON.format(reason=esc(reason)) if reason else ""
    await _notify(bot, uid, t.PLAYER_BANNED.format(duration=duration, reason=reason_line))
    return t.BAN_DURATION_TITLES[key]


@router.callback_query(F.data.startswith(CB_PUNISH_BAN_NO_REASON))
async def cb_ban_no_reason(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_PUNISH_BAN_NO_REASON, protect=True)
    if opened is None or len(opened[0]) != 1 or opened[0][0] not in BAN_DURATIONS:
        return
    user = opened[1]
    title = await _apply_ban(session, callback.bot, callback.from_user.id, user.id, opened[0][0], None)
    await state.clear()
    await back_to_card(callback, session, user.id, t.DONE_BAN.format(duration=title))


@router.message(AdminPunishStates.waiting_reason)
async def on_reason(message: Message, state: FSMContext, session: AsyncSession) -> None:
    admin_id = message.from_user.id
    if not await roles.can(session, admin_id, SECTION_PUNISH):
        await state.clear()
        return
    data = await state.get_data()
    uid, key = data["uid"], data["key"]
    reason = (message.text or "").strip()
    if len(reason) > BAN_REASON_MAX_LEN:
        await message.answer(t.BAN_REASON_TOO_LONG.format(max=BAN_REASON_MAX_LEN), reply_markup=kb.ban_reason(uid, key))
        return
    title = await _apply_ban(session, message.bot, admin_id, uid, key, reason or None)
    await state.clear()
    await reply_card(message, session, uid, t.DONE_BAN.format(duration=title))


@router.callback_query(F.data.startswith(CB_PUNISH_UNBAN))
async def cb_unban(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_PUNISH_UNBAN)
    if opened is None:
        return
    user = opened[1]
    if not players.is_banned(user):
        await callback.answer(t.NOT_BANNED_ALERT, show_alert=True)
        return
    await players_admin.unban(session, user.id)
    await audit.log(session, callback.from_user.id, AUDIT_UNBAN, user.id)
    await session.commit()
    await _notify(callback.bot, user.id, t.PLAYER_UNBANNED)
    await back_to_card(callback, session, user.id, t.DONE_UNBAN)


# ---------------------------- кулдауны / сброс / удаление ----------------------------

@router.callback_query(F.data.startswith(CB_PUNISH_COOLDOWNS))
async def cb_cooldowns(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    opened = await _open(callback, session, CB_PUNISH_COOLDOWNS)
    if opened is None:
        return
    user = opened[1]
    removed = await players_admin.clear_cooldowns(redis, user.id)
    await audit.log(session, callback.from_user.id, AUDIT_CLEAR_COOLDOWNS, user.id, {"keys": removed})
    await session.commit()
    await back_to_card(callback, session, user.id, t.DONE_COOLDOWNS.format(count=removed))


@router.callback_query(F.data.startswith(CB_PUNISH_RESET_ASK))
async def cb_reset_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_PUNISH_RESET_ASK, protect=True)
    if opened is not None:
        await edit_screen(callback, t.RESET_CONFIRM.format(name=name_of(opened[1])), kb.reset_confirm(opened[1].id))


@router.callback_query(F.data.startswith(CB_PUNISH_RESET_YES))
async def cb_reset_yes(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_PUNISH_RESET_YES, protect=True)
    if opened is None:
        return
    user = opened[1]
    await players_admin.reset_progress(session, user.id)
    await audit.log(session, callback.from_user.id, AUDIT_RESET_PLAYER, user.id)
    await session.commit()
    await back_to_card(callback, session, user.id, t.DONE_RESET)


@router.callback_query(F.data.startswith(CB_PUNISH_DELETE_ASK))
async def cb_delete_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_PUNISH_DELETE_ASK, protect=True)
    if opened is not None:
        await edit_screen(callback, t.DELETE_CONFIRM.format(name=name_of(opened[1])), kb.delete_confirm(opened[1].id))


@router.callback_query(F.data.startswith(CB_PUNISH_DELETE_YES))
async def cb_delete_yes(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_PUNISH_DELETE_YES, protect=True)
    if opened is None:
        return
    uid = opened[1].id
    try:
        await players_admin.delete_account(session, uid)
        await audit.log(session, callback.from_user.id, AUDIT_DELETE_ACCOUNT, None, {"deleted_id": uid})
        await session.commit()
    except players_admin.OwnerBlockedError as e:
        await session.rollback()
        await callback.answer(t.DELETE_OWNER_BLOCKED.format(members=e.members), show_alert=True)
        return
    except IntegrityError as e:
        await session.rollback()
        await callback.answer(t.DELETE_FAILED.format(reason=type(e.orig).__name__), show_alert=True)
        return
    await edit_screen(callback, t.DELETED.format(id=uid), back_to_panel())
