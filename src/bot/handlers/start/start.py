"""/start — вход в игру (хендлеры).

Онбординг полностью реализован: страна -> город -> название банды -> профиль (см.
`services/start`, `services/gang`). Остальной флоу карты/развития и т.д. — TODO, ждёт
других доменов (см. CLAUDE.md, "Открытые вопросы дизайна").
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.start import (
    CB_START_BACK_TO_COUNTRY,
    CB_START_CITY_PAGE_PREFIX,
    CB_START_CITY_PREFIX,
    CB_START_COUNTRY_PREFIX,
)
from bot.db.repositories.user import upsert_from_telegram
from bot.handlers.gang import prompt_gang_name
from bot.handlers.profile import show_profile
from bot.keyboards.start import city_menu, country_menu
from bot.services.city import list_cities
from bot.services.gang import get_gang
from bot.services.start import UnknownCityError, UnknownCountryError, finish_onboarding, is_onboarded, resolve_country
from bot.texts.start import CHOOSE_CITY, CHOOSE_COUNTRY, ONBOARDING_DONE, UNKNOWN_CITY, UNKNOWN_COUNTRY

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await upsert_from_telegram(
        session,
        user_id=message.from_user.id,
        username=message.from_user.username,
        display_name=message.from_user.full_name,
    )
    if not is_onboarded(user):
        await message.answer(CHOOSE_COUNTRY, reply_markup=country_menu())
        return

    if await get_gang(session, user.id) is None:
        # Страна/город выбраны, банда — ещё нет (прервался на этом шаге раньше) —
        # дожать онбординг, не показывать профиль без банды.
        await prompt_gang_name(message, state)
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
