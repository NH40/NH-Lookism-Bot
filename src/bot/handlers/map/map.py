"""Карта — город игрока и его районы (хендлеры).

raw-notes «Карта»: игрок в фазе банды видит свой город и его районы — сколько у ботов,
сколько у него, сколько у других игроков; если весь город у одного игрока — это видно.
Круг и выше (подтверждено 2026-09-29) — «🗺 Карта» открывает карту страны: все города с
раскладкой (боты / твои / сколько других игроков), город → экран владельцев с кнопками
боя (боты города — одним боем, игрок — вызов за все его районы в городе). Карта стран
для кулаков — следующий блок.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.map import CB_MAP_CITY_PREFIX, CB_MAP_COUNTRY_PAGE_PREFIX, CB_MAP_OPEN, CB_MAP_PAGE_PREFIX
from bot.db.models.user import User
from bot.db.repositories.user import get_by_id
from bot.keyboards.map import city_map_menu, city_owners_menu, country_map_menu
from bot.services.district import (
    CityNotInCountryError,
    DistrictView,
    get_city_map,
    get_city_owners,
    get_country_map,
    get_influence,
)
from bot.services.extra import get_army_stats
from bot.services.phase import is_city_conqueror, is_emperor
from bot.texts.district import CITY_NOT_FOUND
from bot.texts.map import (
    CITY_EMPEROR_NOTE,
    COUNTRY_MAP_HEADER_EMPEROR,
    BTN_ATTACK_CITY_BOTS,
    BTN_CHALLENGE_OWNER,
    CITY_BOTS_LINE,
    CITY_BTN,
    CITY_BTN_MINE,
    CITY_FULLY_MINE,
    CITY_NO_BOTS_LINE,
    CITY_NO_OWNERS,
    CITY_OWNER_CHALLENGED,
    CITY_OWNER_LINE,
    CITY_OWNER_MINE,
    CITY_SCREEN,
    COUNTRY_MAP_HEADER,
    DISTRICT_BTN_BOT,
    DISTRICT_BTN_MINE,
    DISTRICT_BTN_OTHER,
    MAP_HEADER,
    SOLE_OWNER_LINE,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.formatting import esc, format_number
from bot.utils.safe_edit import safe_edit_text
from bot.keyboards.event import event_rows
from bot.services.event import list_active as list_events
from bot.texts.event import MAP_EVENTS_LINE
from bot.constant.event import EVENT_SCHOOL_TEACHER
from bot.handlers.school import school_button_label
from bot.texts.unique_technique import teacher_button_label

router = Router(name="map")


def _button_label(view: DistrictView) -> str:
    # Подписи inline-кнопок — plain text, не HTML: экранировать название банды не нужно.
    if view.owner_id is None:
        return DISTRICT_BTN_BOT.format(number=view.number, power=format_number(view.bot_power))
    if view.is_mine:
        return DISTRICT_BTN_MINE.format(number=view.number)
    return DISTRICT_BTN_OTHER.format(number=view.number, owner=view.owner_label)


def _teacher_label(event) -> str:
    return school_button_label(event) if event.kind == EVENT_SCHOOL_TEACHER else teacher_button_label(event)


async def _events_block(session: AsyncSession, user_id: int):
    """Метки событий на карте (боссы, учителя): строка в текст и кнопки над районами."""
    events = await list_events(session, user_id)
    rows = event_rows(events, teacher_label=_teacher_label)
    return (MAP_EVENTS_LINE.format(count=len(rows)) if rows else ""), rows


async def show_city_map(message: Message, session: AsyncSession, user: User, page: int, *, edit: bool) -> None:
    """Публичная функция домена — переиспользуется кнопкой "◀️ К карте" из карточки района."""
    city_map = await get_city_map(session, user)
    text = MAP_HEADER.format(
        city=city_map.city_name,
        total=len(city_map.districts),
        mine=city_map.mine,
        bots=city_map.bots,
        others=city_map.others,
        sole=SOLE_OWNER_LINE.format(owner=esc(city_map.sole_owner_label)) if city_map.sole_owner_label else "",
        influence=await get_influence(session, user.id),
    )
    line, rows = await _events_block(session, user.id)
    markup = city_map_menu(
        [(v.id, _button_label(v)) for v in city_map.districts],
        page,
        back_to_country=is_city_conqueror(user.phase),
        top_rows=rows,
    )
    text += line
    if edit:
        await safe_edit_text(message, text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


async def _onboarded_user(session: AsyncSession, user_id: int) -> User | None:
    user = await get_by_id(session, user_id)
    return user if user is not None and user.city_id is not None else None


@router.message(Command("map"))
async def cmd_map(message: Message, session: AsyncSession) -> None:
    user = await _onboarded_user(session, message.from_user.id)
    if user is None:
        await message.answer(NOT_ONBOARDED)
        return
    await _open_map(message, session, user)


async def _open_map(message: Message, session: AsyncSession, user: User) -> None:
    if is_city_conqueror(user.phase):
        await show_country_map(message, session, user, 0, edit=False)
    else:
        await show_city_map(message, session, user, 0, edit=False)


@router.callback_query(F.data == CB_MAP_OPEN)
async def cb_map_open(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await _onboarded_user(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    await _open_map(callback.message, session, user)


@router.callback_query(F.data.startswith(CB_MAP_PAGE_PREFIX))
async def cb_map_page(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await _onboarded_user(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    page = int(callback.data.removeprefix(CB_MAP_PAGE_PREFIX))
    await show_city_map(callback.message, session, user, page, edit=True)


# --- карта страны и экран города (круг и выше) ---


def _city_label(city) -> str:
    if city.fully_mine:
        return CITY_BTN_MINE.format(name=city.name)
    return CITY_BTN.format(name=city.name, bots=city.bots, mine=city.mine, owners=city.owners)


async def show_country_map(message: Message, session: AsyncSession, user: User, page: int, *, edit: bool) -> None:
    country_map = await get_country_map(session, user)
    header = COUNTRY_MAP_HEADER_EMPEROR if is_emperor(user.phase) else COUNTRY_MAP_HEADER
    text = header.format(
        country=country_map.country_name,
        total=len(country_map.cities),
        mine=country_map.cities_mine,
        influence=await get_influence(session, user.id),
    )
    line, rows = await _events_block(session, user.id)
    markup = country_map_menu([(c.city_id, _city_label(c)) for c in country_map.cities], page, top_rows=rows)
    text += line
    if edit:
        await safe_edit_text(message, text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


async def show_city_owners(message: Message, session: AsyncSession, user: User, city_id: int, page: int) -> None:
    """Публичная функция домена — переиспользуется кнопкой «◀️ К городу» из отчёта о бое."""
    view = await get_city_owners(session, user, city_id)
    army = await get_army_stats(session, user.id)
    owner_lines = []
    for owner in view.owners:
        mark = CITY_OWNER_MINE if owner.is_mine else CITY_OWNER_CHALLENGED if owner.challenged else ""
        owner_lines.append(CITY_OWNER_LINE.format(label=esc(owner.label), districts=owner.districts, mark=mark))
    fully_mine = len(view.owners) == 1 and view.owners[0].is_mine and view.bots == 0
    text = CITY_SCREEN.format(
        name=view.name,
        total=view.district_count,
        bots_line=(
            CITY_BOTS_LINE.format(
                districts=view.bots,
                quantity=format_number(view.bot_quantity),
                rank=view.bot_rank,
                power=format_number(view.bot_power),
            )
            if view.bots
            else CITY_NO_BOTS_LINE
        ),
        owners_block="\n".join(owner_lines) if owner_lines else CITY_NO_OWNERS,
        attack_quantity=format_number(army.attack.quantity),
        attack_power=format_number(army.attack.power),
    ) + (CITY_FULLY_MINE if fully_mine else "")
    emperor = is_emperor(user.phase)
    if emperor:
        text += CITY_EMPEROR_NOTE
    # Подписи inline-кнопок — plain text, экранировать название банды не нужно. Императору кнопок
    # захвата нет — свою страну он не берёт (сервис и так откажет, но кнопка путала).
    markup = city_owners_menu(
        view.city_id,
        bots_label=BTN_ATTACK_CITY_BOTS.format(districts=view.bots) if view.bots and not emperor else None,
        owners=[] if emperor else [
            (o.owner_id, BTN_CHALLENGE_OWNER.format(label=o.label, districts=o.districts))
            for o in view.owners
            if not o.is_mine and not o.challenged
        ],
        page=page,
    )
    await safe_edit_text(message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_MAP_COUNTRY_PAGE_PREFIX))
async def cb_country_page(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await _onboarded_user(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        page = int(callback.data.removeprefix(CB_MAP_COUNTRY_PAGE_PREFIX))
    except ValueError:
        page = 0
    await callback.answer()
    await show_country_map(callback.message, session, user, page, edit=True)


@router.callback_query(F.data.startswith(CB_MAP_CITY_PREFIX))
async def cb_city_view(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await _onboarded_user(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        city_raw, page_raw = callback.data.removeprefix(CB_MAP_CITY_PREFIX).split(":")
        city_id, page = int(city_raw), int(page_raw)
    except ValueError:
        await callback.answer()
        return
    try:
        await show_city_owners(callback.message, session, user, city_id, page)
    except CityNotInCountryError:
        await callback.answer(CITY_NOT_FOUND, show_alert=True)
        return
    await callback.answer()
