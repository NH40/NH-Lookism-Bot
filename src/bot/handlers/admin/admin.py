"""Админ-панель — `/admin`, бета-режим по кодовому слову, техрежим (хендлеры).

Весь роутер закрыт `IsAdminFilter` (на уровне роутера, не в каждом хендлере) — не-админам
`/admin` и кнопки панели молча не отвечают, как незнакомая команда (тот же принцип, что в
UAP: не палить сам факт существования админки).

Бета-режим (срочный запрос пользователя 2026-09-30) — см. `services/admin/beta.py`;
пропускает/не пропускает игроков `middlewares/beta_gate.py`.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import tech_mode_flag
from bot.constant.admin import (
    CB_ADMIN_SECTION_PREFIX,
    SECTION_SYSTEM,
    BETA_CODE_MODE_CHANGE,
    BETA_CODE_MODE_ENABLE,
    BETA_CODE_MODE_KEY,
    CB_ADMIN_BETA_CODE,
    CB_ADMIN_BETA_GENERATE,
    CB_ADMIN_BETA_OFF,
    CB_ADMIN_BETA_OFF_ASK,
    CB_ADMIN_BETA_ON,
    CB_ADMIN_OPEN,
    CB_ADMIN_TECH_TOGGLE,
)
from bot.handlers.admin.common import guard
from bot.keyboards.admin import code_prompt_menu, main_menu, off_confirm_menu, panel_menu
from bot.services.admin import beta, roles
from bot.states.admin import AdminStates
from bot.texts.admin import (
    MAIN_PANEL,
    ROLE_NAMES,
    BETA_ALREADY_OFF,
    BETA_ALREADY_ON,
    BETA_CODE_CHANGED,
    BETA_DISABLED,
    BETA_ENABLED,
    BETA_OFF_BLOCK,
    BETA_ON_BLOCK,
    CODE_PROMPT_CHANGE,
    CODE_PROMPT_ENABLE,
    CODE_TOO_LONG,
    CODE_TOO_SHORT,
    OFF_CONFIRM,
    PANEL,
    TECH_OFF,
    TECH_ON,
    TECH_TOGGLED_OFF,
    TECH_TOGGLED_ON,
)
from bot.utils.formatting import esc, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin")  # фильтр IsAdminFilter — на корневом роутере (handlers/admin/__init__)


async def _render_panel(redis: Redis, notice: str | None = None):
    state = await beta.get_state(redis)
    tech_on = bool(await redis.get(tech_mode_flag()))
    beta_block = (
        BETA_ON_BLOCK.format(code=esc(state.code), allowed=format_number(await beta.allowed_count(redis, state)))
        if state
        else BETA_OFF_BLOCK
    )
    text = PANEL.format(beta_block=beta_block, tech=TECH_ON if tech_on else TECH_OFF)
    if notice:
        text = f"{notice}\n\n{text}"
    return text, panel_menu(beta_on=state is not None, tech_on=tech_on)


async def _main_panel(session: AsyncSession, user_id: int):
    role = await roles.role_of(session, user_id)
    return MAIN_PANEL.format(role=ROLE_NAMES.get(role, role)), main_menu(roles.visible_sections(role))


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    text, markup = await _main_panel(session, message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == CB_ADMIN_OPEN)
async def cb_admin_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    # Сюда ведут все «◀️ Назад» к панели — FSM чистим всегда.
    await state.clear()
    await callback.answer()
    text, markup = await _main_panel(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == f"{CB_ADMIN_SECTION_PREFIX}{SECTION_SYSTEM}")
async def cb_system(callback: CallbackQuery, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    """Раздел «Бета и техрежим» — бывшая панель целиком."""
    await state.clear()
    if not await guard(callback, session, SECTION_SYSTEM):
        return
    await callback.answer()
    text, markup = await _render_panel(redis)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_ADMIN_TECH_TOGGLE)
async def cb_admin_tech_toggle(callback: CallbackQuery, redis: Redis) -> None:
    # DEL возвращает 1, если флаг был — значит выключили; иначе включаем.
    turned_off = bool(await redis.delete(tech_mode_flag()))
    if not turned_off:
        await redis.set(tech_mode_flag(), "1")
    await callback.answer(TECH_TOGGLED_OFF if turned_off else TECH_TOGGLED_ON)
    text, markup = await _render_panel(redis)
    await safe_edit_text(callback.message, text, reply_markup=markup)


async def _prompt_code(callback: CallbackQuery, state: FSMContext, mode: str) -> None:
    await state.set_state(AdminStates.waiting_beta_code)
    await state.update_data({BETA_CODE_MODE_KEY: mode})
    await callback.answer()
    await safe_edit_text(
        callback.message,
        CODE_PROMPT_ENABLE if mode == BETA_CODE_MODE_ENABLE else CODE_PROMPT_CHANGE,
        reply_markup=code_prompt_menu(),
    )


@router.callback_query(F.data == CB_ADMIN_BETA_ON)
async def cb_beta_on(callback: CallbackQuery, state: FSMContext, redis: Redis) -> None:
    if await beta.get_state(redis) is not None:
        await callback.answer(BETA_ALREADY_ON, show_alert=True)
        return
    await _prompt_code(callback, state, BETA_CODE_MODE_ENABLE)


@router.callback_query(F.data == CB_ADMIN_BETA_CODE)
async def cb_beta_code(callback: CallbackQuery, state: FSMContext, redis: Redis) -> None:
    if await beta.get_state(redis) is None:
        await callback.answer(BETA_ALREADY_OFF, show_alert=True)
        return
    await _prompt_code(callback, state, BETA_CODE_MODE_CHANGE)


async def _apply_code(redis: Redis, mode: str, code: str) -> tuple[str | None, str | None]:
    """(уведомление для панели, текст ошибки-алерта) — ровно одно из двух не None."""
    if mode == BETA_CODE_MODE_ENABLE:
        result = await beta.enable(redis, code)
        return (BETA_ENABLED.format(code=esc(result.code)), None) if result else (None, BETA_ALREADY_ON)
    result = await beta.change_code(redis, code)
    return (BETA_CODE_CHANGED.format(code=esc(result.code)), None) if result else (None, BETA_ALREADY_OFF)


@router.callback_query(F.data == CB_ADMIN_BETA_GENERATE, AdminStates.waiting_beta_code)
async def cb_beta_generate(callback: CallbackQuery, state: FSMContext, redis: Redis) -> None:
    mode = (await state.get_data()).get(BETA_CODE_MODE_KEY, BETA_CODE_MODE_ENABLE)
    await state.clear()
    notice, error = await _apply_code(redis, mode, beta.generate_code())
    if error:
        await callback.answer(error, show_alert=True)
    else:
        await callback.answer()
    text, markup = await _render_panel(redis, notice)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.message(AdminStates.waiting_beta_code)
async def on_beta_code(message: Message, state: FSMContext, redis: Redis) -> None:
    try:
        code = beta.validate_code(message.text or "")
    except beta.InvalidBetaCodeError as exc:
        await message.answer(CODE_TOO_SHORT if exc.reason == "too_short" else CODE_TOO_LONG,
                             reply_markup=code_prompt_menu())
        return
    mode = (await state.get_data()).get(BETA_CODE_MODE_KEY, BETA_CODE_MODE_ENABLE)
    await state.clear()
    notice, error = await _apply_code(redis, mode, code)
    text, markup = await _render_panel(redis, notice or error)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == CB_ADMIN_BETA_OFF_ASK)
async def cb_beta_off_ask(callback: CallbackQuery, redis: Redis) -> None:
    current = await beta.get_state(redis)
    if current is None:
        await callback.answer(BETA_ALREADY_OFF, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message,
        OFF_CONFIRM.format(allowed=format_number(await beta.allowed_count(redis, current))),
        reply_markup=off_confirm_menu(),
    )


@router.callback_query(F.data == CB_ADMIN_BETA_OFF)
async def cb_beta_off(callback: CallbackQuery, redis: Redis) -> None:
    allowed = await beta.disable(redis)
    if allowed is None:
        await callback.answer(BETA_ALREADY_OFF, show_alert=True)
    else:
        await callback.answer()
    notice = BETA_DISABLED.format(allowed=format_number(allowed)) if allowed is not None else None
    text, markup = await _render_panel(redis, notice)
    await safe_edit_text(callback.message, text, reply_markup=markup)
