"""Админка — Роли (хендлеры). Только супер-админ (SECTION_MIN_ROLE)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import get_settings
from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, ROLES, SECTION_ROLES
from bot.constant.admin.live_config import (
    AUDIT_ROLE_REMOVE,
    AUDIT_ROLE_SET,
    CB_ROLES_ADD,
    CB_ROLES_DEL_ASK_PREFIX,
    CB_ROLES_DEL_PREFIX,
    CB_ROLES_LIST,
    CB_ROLES_SET_PREFIX,
    CB_ROLES_USER_PREFIX,
)
from bot.handlers.admin.common import guard, parse_id
from bot.keyboards.admin.roles_admin import back_to_list, del_confirm_menu, list_menu, user_menu
from bot.services.admin import audit, players, roles
from bot.states.admin_roles import AdminRolesStates
from bot.texts.admin.roles_admin import (
    ADD_PROMPT,
    DEL_CONFIRM,
    DEL_DONE_ALERT,
    NOT_FOUND,
    NOTIFY_REMOVE,
    NOTIFY_SET,
    ROLE_NONE,
    ROLES_EMPTY,
    ROLES_ROW,
    ROLES_ROW_SUPER,
    ROLES_SCREEN,
    SET_DONE_ALERT,
    SUPER_ALERT,
    USER_SCREEN,
)
from bot.texts.admin import ROLE_NAMES
from bot.utils.formatting import esc
from bot.utils.notify import notify
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_roles")


def _name(user) -> str:
    return f"@{user.username}" if user.username else esc(user.display_name or str(user.id))


async def _show_list(callback: CallbackQuery, session: AsyncSession) -> None:
    staff = await roles.list_staff(session)
    supers = sorted(get_settings().admin_ids)
    rows = [ROLES_ROW_SUPER.format(uid=uid) for uid in supers]
    rows += [ROLES_ROW.format(role=ROLE_NAMES.get(role, role), name=f"@{name}" if name else "—", uid=uid) for uid, name, role in staff]
    await safe_edit_text(
        callback.message,
        ROLES_SCREEN.format(rows="\n".join(rows) if rows else ROLES_EMPTY),
        reply_markup=list_menu(staff),
    )


@router.callback_query(F.data.in_({f"{CB_ADMIN_SECTION_PREFIX}{SECTION_ROLES}", CB_ROLES_LIST}))
async def cb_section(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_ROLES):
        return
    await state.clear()
    await callback.answer()
    await _show_list(callback, session)


@router.callback_query(F.data == CB_ROLES_ADD)
async def cb_add(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_ROLES):
        return
    await callback.answer()
    await state.set_state(AdminRolesStates.waiting_target)
    await safe_edit_text(callback.message, ADD_PROMPT, reply_markup=back_to_list())


@router.message(AdminRolesStates.waiting_target, F.text)
async def msg_target(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_ROLES):
        await state.clear()
        return
    user = await players.find(session, message.text)
    if user is None:
        await message.answer(NOT_FOUND.format(query=esc(message.text[:40])), reply_markup=back_to_list())
        return
    await state.clear()
    await _user_screen(message, session, user.id, edit=False)


async def _user_screen(target, session: AsyncSession, uid: int, *, edit: bool) -> None:
    user = await players.get_by_id(session, uid)
    role = await roles.role_of(session, uid)
    text = USER_SCREEN.format(name=_name(user), uid=uid, role=ROLE_NAMES.get(role, ROLE_NONE) if role else ROLE_NONE)
    markup = user_menu(uid, role is not None)
    if edit:
        await safe_edit_text(target, text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_ROLES_USER_PREFIX))
async def cb_user(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_ROLES):
        return
    uid = parse_id(callback.data, CB_ROLES_USER_PREFIX)
    if uid is None or await players.get_by_id(session, uid) is None:
        await callback.answer()
        return
    await callback.answer()
    await _user_screen(callback.message, session, uid, edit=True)


@router.callback_query(F.data.startswith(CB_ROLES_SET_PREFIX))
async def cb_set(callback: CallbackQuery, session: AsyncSession, bot) -> None:
    if not await guard(callback, session, SECTION_ROLES):
        return
    uid_raw, _, role = callback.data.removeprefix(CB_ROLES_SET_PREFIX).partition(":")
    if not uid_raw.isdigit() or role not in ROLES:
        await callback.answer()
        return
    uid = int(uid_raw)
    if uid in get_settings().admin_ids:
        await callback.answer(SUPER_ALERT, show_alert=True)
        return
    if not await roles.set_role(session, uid, role):
        await callback.answer()
        return
    await audit.log(session, callback.from_user.id, AUDIT_ROLE_SET, uid, {"role": role})
    await session.commit()
    await callback.answer(SET_DONE_ALERT)
    await notify(bot, uid, NOTIFY_SET.format(role=ROLE_NAMES[role]))
    await _user_screen(callback.message, session, uid, edit=True)


@router.callback_query(F.data.startswith(CB_ROLES_DEL_ASK_PREFIX))
async def cb_del_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_ROLES):
        return
    uid = parse_id(callback.data, CB_ROLES_DEL_ASK_PREFIX)
    user = await players.get_by_id(session, uid) if uid is not None else None
    if user is None:
        await callback.answer()
        return
    if uid in get_settings().admin_ids:
        await callback.answer(SUPER_ALERT, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, DEL_CONFIRM.format(name=_name(user), uid=uid), reply_markup=del_confirm_menu(uid))


@router.callback_query(F.data.startswith(CB_ROLES_DEL_PREFIX))
async def cb_del(callback: CallbackQuery, session: AsyncSession, bot) -> None:
    if not await guard(callback, session, SECTION_ROLES):
        return
    uid = parse_id(callback.data, CB_ROLES_DEL_PREFIX)
    if uid is None:
        await callback.answer()
        return
    if uid in get_settings().admin_ids:
        await callback.answer(SUPER_ALERT, show_alert=True)
        return
    await roles.set_role(session, uid, None)
    await audit.log(session, callback.from_user.id, AUDIT_ROLE_REMOVE, uid, {})
    await session.commit()
    await callback.answer(DEL_DONE_ALERT)
    await notify(bot, uid, NOTIFY_REMOVE)
    await _show_list(callback, session)
