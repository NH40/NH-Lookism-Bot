"""Админка — Рассылка (фильтры, текст/фото/кнопка, превью, фон батчами) и массовая выдача."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, SECTION_MASS
from bot.constant.admin.mass import (
    BROADCAST_CAPTION_LIMIT,
    BROADCAST_TEXT_LIMIT,
    CB_MASS_BROADCAST,
    CB_MASS_BROADCAST_GO,
    CB_MASS_FILTER_PREFIX,
    CB_MASS_GRANT,
    CB_MASS_GRANT_GO,
    CB_MASS_RES_PREFIX,
    CB_MASS_SKIP_BUTTON,
    FILTERS,
    FLT_CLAN,
    KEY_AMOUNT,
    KEY_CLAN_ID,
    KEY_CLAN_NAME,
    KEY_CONTENT,
    KEY_FILTER,
    KEY_MODE,
    KEY_RESOURCE,
    MASS_GRANT_MAX_AMOUNT,
    MODE_BROADCAST,
    MODE_GRANT,
)
from bot.constant.resource import RESOURCES
from bot.handlers.admin.common import guard
from bot.keyboards.admin import mass as kb
from bot.services.admin import audit, roles
from bot.services.admin import mass as mass_service
from bot.states.admin_mass import AdminMassStates
from bot.texts.admin import mass as tx
from bot.texts.resource import amount_label, resource_label
from bot.utils.formatting import esc, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_mass")
log = logging.getLogger(__name__)
# Ссылки на фоновые рассылки — иначе GC может собрать задачу посреди выполнения.
_background_tasks: set[asyncio.Task] = set()


def _audience(data: dict) -> mass_service.Audience:
    return mass_service.Audience(data[KEY_FILTER], data.get(KEY_CLAN_ID))


def _audience_label(data: dict) -> str:
    label = tx.FILTER_LABELS[data[KEY_FILTER]]
    if data.get(KEY_CLAN_NAME):
        label += f": {esc(data[KEY_CLAN_NAME])}"
    return label


async def _can(session: AsyncSession, user_id: int) -> bool:
    return await roles.can(session, user_id, SECTION_MASS)


@router.callback_query(F.data == f"{CB_ADMIN_SECTION_PREFIX}{SECTION_MASS}")
async def cb_section(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_MASS):
        return
    await state.clear()
    await callback.answer()
    await safe_edit_text(callback.message, tx.MENU, reply_markup=kb.menu())


@router.callback_query(F.data.in_({CB_MASS_BROADCAST, CB_MASS_GRANT}))
async def cb_mode(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_MASS):
        return
    broadcast = callback.data == CB_MASS_BROADCAST
    await state.clear()
    await state.update_data({KEY_MODE: MODE_BROADCAST if broadcast else MODE_GRANT})
    await callback.answer()
    await safe_edit_text(
        callback.message,
        tx.PICK_FILTER.format(title=tx.TITLE_BROADCAST if broadcast else tx.TITLE_GRANT),
        reply_markup=kb.filter_menu(),
    )


async def _after_audience(message: Message, session: AsyncSession, state: FSMContext, *, edit: bool) -> None:
    data = await state.get_data()
    aud = _audience(data)
    count = await mass_service.count_audience(session, aud)
    label = _audience_label(data)
    if data[KEY_MODE] == MODE_BROADCAST:
        await state.set_state(AdminMassStates.waiting_content)
        text, markup = tx.CONTENT_PROMPT.format(audience=label, count=format_number(count)), kb.back()
    else:
        await state.set_state(None)
        text, markup = tx.PICK_RESOURCE.format(audience=label, count=format_number(count)), kb.resource_menu()
    if edit:
        await safe_edit_text(message, text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_MASS_FILTER_PREFIX))
async def cb_filter(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_MASS):
        return
    code = callback.data.removeprefix(CB_MASS_FILTER_PREFIX)
    data = await state.get_data()
    if code not in FILTERS or KEY_MODE not in data:
        await callback.answer(tx.STATE_LOST_ALERT, show_alert=True)
        return
    await state.update_data({KEY_FILTER: code, KEY_CLAN_ID: None, KEY_CLAN_NAME: None})
    await callback.answer()
    if code == FLT_CLAN:
        await state.set_state(AdminMassStates.waiting_clan)
        await safe_edit_text(callback.message, tx.CLAN_PROMPT, reply_markup=kb.back())
        return
    await _after_audience(callback.message, session, state, edit=True)


@router.message(StateFilter(AdminMassStates.waiting_clan), F.text, ~F.text.startswith("/"))
async def apply_clan(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await _can(session, message.from_user.id):
        return
    clan = await mass_service.find_clan(session, message.text)
    if clan is None:
        await message.answer(tx.CLAN_NOT_FOUND, reply_markup=kb.back())
        return
    await state.update_data({KEY_CLAN_ID: clan.id, KEY_CLAN_NAME: clan.name})
    await _after_audience(message, session, state, edit=False)


# ---------------------------------------------------------------- рассылка

@router.message(StateFilter(AdminMassStates.waiting_content), F.photo | F.text, ~F.text.startswith("/"))
async def apply_content(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await _can(session, message.from_user.id):
        return
    if message.photo:
        text = message.html_text if message.caption else ""
        content = mass_service.Content(text=text, photo=message.photo[-1].file_id)
        limit = BROADCAST_CAPTION_LIMIT
    else:
        content = mass_service.Content(text=message.html_text)
        limit = BROADCAST_TEXT_LIMIT
    if (not content.text and not content.photo) or len(content.text) > limit:
        await message.answer(tx.CONTENT_BAD, reply_markup=kb.back())
        return
    await state.update_data({KEY_CONTENT: content.to_dict()})
    await state.set_state(AdminMassStates.waiting_button)
    await message.answer(tx.BUTTON_PROMPT, reply_markup=kb.skip_button_menu())


async def _send_preview(message: Message, bot: Bot, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    content = mass_service.Content.from_dict(data[KEY_CONTENT])
    count = await mass_service.count_audience(session, _audience(data))
    await state.set_state(None)
    await mass_service.send_content(bot, message.chat.id, content)
    await message.answer(
        tx.PREVIEW_CONFIRM.format(audience=_audience_label(data), count=format_number(count)),
        reply_markup=kb.broadcast_confirm_menu(),
    )


@router.message(StateFilter(AdminMassStates.waiting_button), F.text, ~F.text.startswith("/"))
async def apply_button(message: Message, session: AsyncSession, state: FSMContext, bot: Bot) -> None:
    if not await _can(session, message.from_user.id):
        return
    parsed = mass_service.parse_button(message.text)
    if parsed is None:
        await message.answer(tx.BUTTON_BAD, reply_markup=kb.skip_button_menu())
        return
    data = await state.get_data()
    content = {**data[KEY_CONTENT], "btn_text": parsed[0], "btn_url": parsed[1]}
    await state.update_data({KEY_CONTENT: content})
    await _send_preview(message, bot, session, state)


@router.callback_query(F.data == CB_MASS_SKIP_BUTTON)
async def cb_skip_button(callback: CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot) -> None:
    if not await guard(callback, session, SECTION_MASS):
        return
    if KEY_CONTENT not in await state.get_data():
        await callback.answer(tx.STATE_LOST_ALERT, show_alert=True)
        return
    await callback.answer()
    await _send_preview(callback.message, bot, session, state)


async def _run_and_report(
    bot: Bot, session_factory: async_sessionmaker[AsyncSession], aud: mass_service.Audience,
    content: mass_service.Content, label: str, admin_chat_id: int,
) -> None:
    try:
        sent, failed = await mass_service.run_broadcast(bot, session_factory, aud, content)
    except Exception:
        log.exception("Broadcast failed")
        await _notify_admin(bot, admin_chat_id, tx.BROADCAST_FAILED)
        return
    await _notify_admin(bot, admin_chat_id, tx.BROADCAST_REPORT.format(audience=label, sent=sent, failed=failed))


async def _notify_admin(bot: Bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except Exception:
        log.exception("Cannot deliver broadcast report")


@router.callback_query(F.data == CB_MASS_BROADCAST_GO)
async def cb_broadcast_go(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not await guard(callback, session, SECTION_MASS):
        return
    data = await state.get_data()
    await state.clear()  # повторный клик не запустит рассылку второй раз
    if KEY_CONTENT not in data:
        await callback.answer(tx.STATE_LOST_ALERT, show_alert=True)
        return
    aud = _audience(data)
    content = mass_service.Content.from_dict(data[KEY_CONTENT])
    count = await mass_service.count_audience(session, aud)
    await audit.log(
        session, callback.from_user.id, "mass_broadcast", None,
        {**mass_service.audience_details(aud), "recipients": count, "photo": bool(content.photo), "text": content.text[:200]},
    )
    await session.commit()
    await callback.answer()
    await safe_edit_text(callback.message, tx.BROADCAST_STARTED.format(count=format_number(count)), reply_markup=kb.back())
    task = asyncio.create_task(
        _run_and_report(bot, session_factory, aud, content, _audience_label(data), callback.from_user.id)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


# ---------------------------------------------------------- массовая выдача

@router.callback_query(F.data.startswith(CB_MASS_RES_PREFIX))
async def cb_resource(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_MASS):
        return
    code = callback.data.removeprefix(CB_MASS_RES_PREFIX)
    if code not in RESOURCES or KEY_FILTER not in await state.get_data():
        await callback.answer(tx.STATE_LOST_ALERT, show_alert=True)
        return
    await state.update_data({KEY_RESOURCE: code})
    await state.set_state(AdminMassStates.waiting_amount)
    await callback.answer()
    await safe_edit_text(
        callback.message,
        tx.AMOUNT_PROMPT.format(resource=resource_label(code), limit=format_number(MASS_GRANT_MAX_AMOUNT)),
        reply_markup=kb.back(),
    )


@router.message(StateFilter(AdminMassStates.waiting_amount), F.text, ~F.text.startswith("/"))
async def apply_amount(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await _can(session, message.from_user.id):
        return
    raw = message.text.strip().replace(" ", "")
    if not raw.isdigit() or not 0 < int(raw) <= MASS_GRANT_MAX_AMOUNT:
        await message.answer(tx.AMOUNT_BAD.format(limit=format_number(MASS_GRANT_MAX_AMOUNT)), reply_markup=kb.back())
        return
    amount = int(raw)
    await state.update_data({KEY_AMOUNT: amount})
    await state.set_state(None)
    data = await state.get_data()
    count = await mass_service.count_audience(session, _audience(data))
    await message.answer(
        tx.GRANT_CONFIRM.format(
            audience=_audience_label(data), count=format_number(count), amount=amount_label(data[KEY_RESOURCE], amount)
        ),
        reply_markup=kb.grant_confirm_menu(),
    )


@router.callback_query(F.data == CB_MASS_GRANT_GO)
async def cb_grant_go(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_MASS):
        return
    data = await state.get_data()
    await state.clear()
    if KEY_AMOUNT not in data or KEY_RESOURCE not in data:
        await callback.answer(tx.STATE_LOST_ALERT, show_alert=True)
        return
    affected = await mass_service.mass_grant(
        session, callback.from_user.id, _audience(data), data[KEY_RESOURCE], data[KEY_AMOUNT]
    )
    await callback.answer()
    await safe_edit_text(callback.message, tx.GRANT_DONE.format(affected=format_number(affected)), reply_markup=kb.back())
