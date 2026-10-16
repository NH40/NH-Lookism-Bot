"""Админка — Настройки на лету (хендлеры). Только супер-админ."""
from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, SECTION_CONFIG
from bot.constant.admin.live_config import (
    CB_CONFIG_DUR_PREFIX,
    CB_CONFIG_KEY_PREFIX,
    CB_CONFIG_LIST,
    CB_CONFIG_RESET_PREFIX,
    CB_CONFIG_SET_PREFIX,
    CONFIG_DURATIONS,
)
from bot.handlers.admin.common import guard
from bot.keyboards.admin.live_config import back_to_key, duration_menu, key_menu, list_menu
from bot.services.admin import live_config, roles
from bot.states.admin_roles import AdminConfigStates
from bot.texts.admin.live_config import (
    BTN_ROW,
    DURATION_PROMPT,
    FOREVER,
    KEY_SCREEN,
    MENU,
    RESET_DONE_ALERT,
    SAVED,
    STAR_FOREVER,
    STAR_LEFT,
    VALUE_BAD,
    VALUE_PROMPT,
)
from bot.utils.formatting import esc, format_countdown
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_live_config")


def _fmt(value) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


def _star(key: str, *, long: bool) -> str:
    entry = live_config.override(key)
    if entry is None:
        return ""
    if entry[1] is None:
        return STAR_FOREVER if long else "★ "
    left = max(int((entry[1] - datetime.now(timezone.utc)).total_seconds()), 0)
    return STAR_LEFT.format(left=format_countdown(left)) if long else "★ "


async def _show_list(message) -> None:
    rows = [
        (k, BTN_ROW.format(star=_star(k, long=False), title=spec.title, value=_fmt(live_config.get(k))))
        for k, spec in live_config.LIVE_KEYS.items()
    ]
    await safe_edit_text(message, MENU, reply_markup=list_menu(rows))


async def _show_key(message, key: str) -> None:
    spec = live_config.LIVE_KEYS[key]
    text = KEY_SCREEN.format(
        title=spec.title,
        value=_fmt(live_config.get(key)),
        star=_star(key, long=True),
        default=_fmt(spec.default()),
        min=_fmt(spec.min),
        max=_fmt(spec.max),
    )
    await safe_edit_text(message, text, reply_markup=key_menu(key, live_config.override(key) is not None))


@router.callback_query(F.data.in_({f"{CB_ADMIN_SECTION_PREFIX}{SECTION_CONFIG}", CB_CONFIG_LIST}))
async def cb_section(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_CONFIG):
        return
    await state.clear()
    await callback.answer()
    await _show_list(callback.message)


@router.callback_query(F.data.startswith(CB_CONFIG_KEY_PREFIX))
async def cb_key(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_CONFIG):
        return
    key = callback.data.removeprefix(CB_CONFIG_KEY_PREFIX)
    if key not in live_config.LIVE_KEYS:
        await callback.answer()
        return
    await state.clear()
    await callback.answer()
    await _show_key(callback.message, key)


@router.callback_query(F.data.startswith(CB_CONFIG_SET_PREFIX))
async def cb_set(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_CONFIG):
        return
    key = callback.data.removeprefix(CB_CONFIG_SET_PREFIX)
    spec = live_config.LIVE_KEYS.get(key)
    if spec is None:
        await callback.answer()
        return
    await callback.answer()
    await state.set_state(AdminConfigStates.waiting_value)
    await state.update_data(key=key)
    await safe_edit_text(
        callback.message,
        VALUE_PROMPT.format(title=spec.title, min=_fmt(spec.min), max=_fmt(spec.max)),
        reply_markup=back_to_key(key),
    )


@router.message(AdminConfigStates.waiting_value, F.text)
async def msg_value(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_CONFIG):
        await state.clear()
        return
    key = (await state.get_data()).get("key")
    spec = live_config.LIVE_KEYS.get(key)
    if spec is None:
        await state.clear()
        return
    value = live_config.validate(key, message.text)
    if value is None:
        await message.answer(VALUE_BAD.format(min=_fmt(spec.min), max=_fmt(spec.max)), reply_markup=back_to_key(key))
        return
    if spec.expiring:
        await state.update_data(value=value)
        await message.answer(DURATION_PROMPT.format(value=_fmt(value), title=spec.title), reply_markup=duration_menu(key))
        return
    await state.clear()
    await live_config.set_value(session, message.from_user.id, key, value)
    await message.answer(
        SAVED.format(title=spec.title, value=_fmt(value), duration=FOREVER), reply_markup=back_to_key(key)
    )


@router.callback_query(F.data.startswith(CB_CONFIG_DUR_PREFIX))
async def cb_duration(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_CONFIG):
        return
    key, _, hours_raw = callback.data.removeprefix(CB_CONFIG_DUR_PREFIX).partition(":")
    spec = live_config.LIVE_KEYS.get(key)
    data = await state.get_data()
    if spec is None or not hours_raw.isdigit() or data.get("key") != key or "value" not in data:
        await callback.answer()
        return
    hours = int(hours_raw)
    value = data["value"]
    await state.clear()
    await live_config.set_value(session, callback.from_user.id, key, value, hours)
    label = dict(CONFIG_DURATIONS).get(hours, FOREVER)
    await callback.answer()
    await safe_edit_text(
        callback.message,
        SAVED.format(title=esc(spec.title), value=_fmt(value), duration=label),
        reply_markup=back_to_key(key),
    )


@router.callback_query(F.data.startswith(CB_CONFIG_RESET_PREFIX))
async def cb_reset(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_CONFIG):
        return
    key = callback.data.removeprefix(CB_CONFIG_RESET_PREFIX)
    if key not in live_config.LIVE_KEYS:
        await callback.answer()
        return
    await live_config.reset(session, callback.from_user.id, key)
    await callback.answer(RESET_DONE_ALERT)
    await _show_key(callback.message, key)
