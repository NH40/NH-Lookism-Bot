"""/start — вход в игру (хендлеры).

Онбординг полностью реализован: страна -> город -> название банды -> профиль (см.
`services/start`, `services/gang`). Остальной флоу карты/развития и т.д. — TODO, ждёт
других доменов (см. CLAUDE.md, "Открытые вопросы дизайна").
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.start import (
    CB_START_BACK_TO_COUNTRY,
    CB_START_CITY_PAGE_PREFIX,
    CB_START_CITY_PREFIX,
    CB_START_COUNTRY_PREFIX,
)
from bot.services.admin.live_config import get as live_get
from bot.db.repositories.user import get_by_id, upsert_from_telegram
from bot.services.referral import record_visit
from bot.services.donate import claim_lbp1
from bot.texts.donate import LBP1_DONATE_CREDITED
from bot.utils.formatting import format_number
from bot.services.characteristic import roll_potential
from bot.handlers.gang import prompt_gang_name
from bot.handlers.profile import show_profile
from bot.keyboards.start import city_menu, country_menu
from bot.services.city import list_cities
from bot.services.gang import get_gang
from bot.services.start import UnknownCityError, UnknownCountryError, finish_onboarding, is_onboarded, resolve_country
from bot.handlers.bloodline import prompt_bloodline
from bot.services.genius import ensure_genius
from bot.texts.genius import FIRST_GENIUS, GENIUS_NAMES
from bot.texts.start import CHOOSE_CITY, CHOOSE_COUNTRY, ONBOARDING_DONE, UNKNOWN_CITY, UNKNOWN_COUNTRY

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext, command: CommandObject) -> None:
    is_new = await get_by_id(session, message.from_user.id) is None
    user = await upsert_from_telegram(
        session,
        user_id=message.from_user.id,
        username=message.from_user.username,
        display_name=message.from_user.full_name,
        starting_nh_coins=live_get("starting_nh_coins"),
        starting_tickets=live_get("starting_tickets"),
        # Потенциал — случайная стадия при регистрации (на ON CONFLICT не трогается).
        starting_potential=roll_potential(),
    )
    if is_new and command.args:
        await record_visit(session, user.id, command.args)  # реферальная кампания админа
    lbp1_coins = await claim_lbp1(session, user.id)  # донат из LBP 1.3, если был
    if lbp1_coins:
        await message.answer(LBP1_DONATE_CREDITED.format(coins=format_number(lbp1_coins)))
    if not is_onboarded(user):
        await message.answer(CHOOSE_COUNTRY, reply_markup=country_menu())
        return

    if await get_gang(session, user.id) is None:
        # Страна/город выбраны, банда — ещё нет (прервался на этом шаге раньше) —
        # дожать онбординг, не показывать профиль без банды.
        await prompt_gang_name(message, state)
        return

    # Первая гениальность — случайно (пользователь 2026-10-02); зарегистрированным раньше —
    # при первом /start после её появления.
    granted = await ensure_genius(session, user.id)
    if granted:
        await message.answer(FIRST_GENIUS.format(name=GENIUS_NAMES[granted]))

    if user.bloodline is None:
        # Банда есть, родословной нет (прервался на этом шаге или зарегистрировался до
        # её появления) — сначала выбор, профиль потом.
        await prompt_bloodline(message)
        return

    # Тот же переход, что в Universe Anime Planet — "/start у существующего игрока
    # открывает профиль", не повторяет приветствие/выбор страны.
    await show_profile(message, session, user.id)


@router.callback_query(F.data.startswith(CB_START_COUNTRY_PREFIX))
async def cb_choose_country(callback: CallbackQuery, session: AsyncSession) -> None:
    code = callback.data.removeprefix(CB_START_COUNTRY_PREFIX)
    try:
        resolve_country(code)
    except UnknownCountryError:
        await callback.answer(UNKNOWN_COUNTRY, show_alert=True)
        return
    await _show_city_page(callback, session, country_code=code, page=0)


@router.callback_query(F.data.startswith(CB_START_CITY_PAGE_PREFIX))
async def cb_city_page(callback: CallbackQuery, session: AsyncSession) -> None:
    payload = callback.data.removeprefix(CB_START_CITY_PAGE_PREFIX)
    country_code, _, page_raw = payload.partition(":")
    await _show_city_page(callback, session, country_code=country_code, page=int(page_raw))


@router.callback_query(F.data == CB_START_BACK_TO_COUNTRY)
async def cb_back_to_country(callback: CallbackQuery) -> None:
    await callback.message.edit_text(CHOOSE_COUNTRY, reply_markup=country_menu())
    await callback.answer()


@router.callback_query(F.data.startswith(CB_START_CITY_PREFIX))
async def cb_choose_city(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    city_id = int(callback.data.removeprefix(CB_START_CITY_PREFIX))
    try:
        city = await finish_onboarding(session, callback.from_user.id, city_id)
    except UnknownCityError:
        await callback.answer(UNKNOWN_CITY, show_alert=True)
        return
    country = resolve_country(city.country_code)
    await callback.message.edit_text(
        ONBOARDING_DONE.format(country=country.name, city=city.name),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[]),  # правило 11 — убрать старые кнопки
    )
    await callback.answer()
    # Страна+город готовы — сразу же дожимаем последний шаг онбординга, отдельным
    # сообщением (edit_text выше — это подтверждение выбора города, не место для нового
    # вопроса).
    await prompt_gang_name(callback.message, state)


async def _show_city_page(callback: CallbackQuery, session: AsyncSession, *, country_code: str, page: int) -> None:
    cities = await list_cities(session, country_code)
    country = resolve_country(country_code)
    await callback.message.edit_text(
        f"{CHOOSE_CITY}\n\n🌍 {country.name}",
        reply_markup=city_menu(country_code, cities, page),
    )
    await callback.answer()
