"""Админка — поиск и карточка игрока (хендлеры). Из карточки — действия других разделов
(выдача, развитие, наказания, журнал), каждое по правам роли."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin import (
    CB_ADMIN_FIND,
    CB_ADMIN_PLAYER_PREFIX,
    CB_ADMIN_SECTION_PREFIX,
    SECTION_DEV,
    SECTION_GIVE,
    SECTION_LOGS,
    SECTION_PLAYERS,
    SECTION_PUNISH,
)
from bot.handlers.admin.common import guard, parse_id
from bot.keyboards.admin import back_to_panel, player_menu
from bot.services.admin import players, roles
from bot.states.admin import AdminStates
from bot.texts.admin import (
    CARD_BAN_FOREVER,
    CARD_BAN_REASON,
    CARD_BAN_UNTIL,
    CARD_NONE,
    CARD_PREMIUM,
    CARD_ROLE,
    FIND_NOT_FOUND,
    FIND_PROMPT,
    PLAYER_CARD,
    PLAYER_NOT_FOUND_ALERT,
    ROLE_NAMES,
)
from bot.texts.bloodline import BLOODLINE_NAMES
from bot.texts.genius import GENIUS_NAMES
from bot.texts.resource import amount_label, resource_label
from bot.texts.unique_path import PATH_NAMES
from bot.texts.unique_technique import TECHNIQUE_NAMES
from bot.utils.formatting import esc, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_players")


def _levels(items: list[tuple[str, int]], names: dict[str, str], active: str | None = None, active2: str | None = None) -> str:
    if not items:
        return CARD_NONE
    marks = {active: "★", active2: "☆"}
    return ", ".join(f"{marks.get(code, '')}{names.get(code, code)} {lvl}" for code, lvl in items)


async def render_card(session: AsyncSession, admin_id: int, user_id: int):
    """(текст, клавиатура) карточки игрока; None — не найден. Публичная: разделы действий
    возвращаются в карточку после изменения."""
    card = await players.card(session, user_id)
    if card is None:
        return None
    u = card.user
    ban = ""
    if card.banned:
        reason = CARD_BAN_REASON.format(reason=esc(u.ban_reason)) if u.ban_reason else ""
        ban = CARD_BAN_FOREVER.format(reason=reason) if u.is_banned else CARD_BAN_UNTIL.format(
            until=u.banned_until.strftime("%d.%m.%Y %H:%M UTC"), reason=reason
        )
    bloodline = f"{BLOODLINE_NAMES.get(u.bloodline, u.bloodline)} {u.bloodline_level}" if u.bloodline else CARD_NONE
    if u.bloodline2:
        bloodline += f" + {BLOODLINE_NAMES.get(u.bloodline2, u.bloodline2)} {u.bloodline2_level}"
    text = PLAYER_CARD.format(
        name=esc(u.display_name or u.username or str(u.id)), id=u.id,
        username=f" · @{esc(u.username)}" if u.username else "",
        role=CARD_ROLE.format(role=ROLE_NAMES.get(card.role, card.role)) if card.role else "", ban=ban,
        gang=esc(card.gang) if card.gang else CARD_NONE, city=esc(card.city) if card.city else CARD_NONE,
        districts=card.districts, clan=esc(card.clan) if card.clan else CARD_NONE,
        last_active=u.last_active_at.strftime("%d.%m.%Y %H:%M UTC") if u.last_active_at else CARD_NONE,
        resources="\n".join(f"{resource_label(code)}: <b>{amount_label(code, amount)}</b>" for code, amount in card.resources.items()),
        bloodline=bloodline,
        paths=_levels(card.paths, PATH_NAMES, u.active_path, u.active_path2),
        techniques=_levels(card.techniques, TECHNIQUE_NAMES, u.active_technique),
        geniuses=_levels(card.geniuses, GENIUS_NAMES, u.active_genius),
        awakening=u.awakening_level, potential=esc(u.potential or CARD_NONE),
        body="✅" if u.second_body else CARD_NONE,
        bp_level=card.bp_level, bp_premium=CARD_PREMIUM if card.bp_premium else "",
        donated=format_number(card.donated_rub), unlocks=card.donate_unlocks,
    )
    role = await roles.role_of(session, admin_id)
    markup = player_menu(
        user_id,
        give=roles.allowed(role, SECTION_GIVE), dev=roles.allowed(role, SECTION_DEV),
        punish=roles.allowed(role, SECTION_PUNISH), logs=roles.allowed(role, SECTION_LOGS),
        phase=u.phase,
    )
    await session.commit()  # сезон пасса мог открыться при чтении
    return text, markup


@router.callback_query(F.data.in_({f"{CB_ADMIN_SECTION_PREFIX}{SECTION_PLAYERS}", CB_ADMIN_FIND}))
async def cb_find(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_PLAYERS):
        return
    await state.set_state(AdminStates.waiting_player_query)
    await callback.answer()
    await safe_edit_text(callback.message, FIND_PROMPT, reply_markup=back_to_panel())


@router.message(AdminStates.waiting_player_query)
async def on_find(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_PLAYERS):
        await state.clear()
        return
    query = (message.text or "").strip()
    user = await players.find(session, query)
    if user is None:
        await message.answer(FIND_NOT_FOUND.format(query=esc(query)), reply_markup=back_to_panel())
        return
    await state.clear()
    text, markup = await render_card(session, message.from_user.id, user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_ADMIN_PLAYER_PREFIX))
async def cb_card(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user_id = parse_id(callback.data, CB_ADMIN_PLAYER_PREFIX)
    if user_id is None or not await guard(callback, session, SECTION_PLAYERS):
        await callback.answer()
        return
    await state.clear()
    rendered = await render_card(session, callback.from_user.id, user_id)
    if rendered is None:
        await callback.answer(PLAYER_NOT_FOUND_ALERT, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, rendered[0], reply_markup=rendered[1])
