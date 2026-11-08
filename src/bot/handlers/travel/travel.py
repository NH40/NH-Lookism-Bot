"""Переезд: экран, выбор страны и города, отказ от районов (хендлеры).

Вход — кнопка «🧳 Переезд» на карте. Права и правила перепроверяет сервис на каждом действии:
экран мог висеть в чате, пока у игрока поменялись районы или фаза."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.country import COUNTRY_BY_CODE
from bot.constant.travel import (
    CB_TRAVEL_ABANDON,
    CB_TRAVEL_ABANDON_ASK,
    CB_TRAVEL_CITIES_PREFIX,
    CB_TRAVEL_COUNTRIES,
    CB_TRAVEL_GO_PREFIX,
    CB_TRAVEL_OPEN,
    CB_TRAVEL_PICK_PREFIX,
)
from bot.keyboards.travel import abandon_menu, after_move_menu, cities_menu, confirm_menu, countries_menu, travel_menu
from bot.services.city import get_city, list_cities
from bot.services.country import CountryEntryClosedError, closed_entries
from bot.services.travel import (
    ChallengePendingError,
    CityMoveCooldownError,
    CountrySwapCooldownError,
    EmperorCannotLeaveError,
    HasDistrictsError,
    LossesNotConfirmedError,
    NoDistrictsError,
    NotOnboardedError,
    SameCityError,
    TravelStatus,
    UnknownCityError,
    abandon_districts,
    check_move,
    get_status,
    move,
)
from bot.texts.country import COUNTRY_CLOSED_ALERT
from bot.texts.travel import (
    ABANDON_ASK,
    ABANDONED,
    CONFIRM_COUNTRY,
    CHALLENGE_LINE,
    CHALLENGE_PENDING_ALERT,
    CITY_COOLDOWN_ALERT,
    CITY_COOLDOWN_LINE,
    CONFIRM_LOSSES,
    COOLDOWN_ALERT,
    COOLDOWN_LINE,
    EMPEROR_ALERT,
    HAS_DISTRICTS_ALERT,
    HOLDINGS_TAIL,
    MOVED,
    MOVED_LOST,
    NO_DISTRICTS_ALERT,
    NOT_ONBOARDED_ALERT,
    PICK_CITY,
    PICK_COUNTRY,
    RULES_CIRCLE,
    RULES_EMPEROR,
    RULES_GANG,
    RULES_GANG_DISTRICTS,
    RULES_INTERVAL_LINE,
    SAME_CITY_ALERT,
    TRAVEL_SCREEN,
    UNKNOWN_CITY_ALERT,
)
from bot.constant.phase import PHASE_CIRCLE
from bot.utils.formatting import format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="travel")


def interval_label(seconds: int) -> str:
    if seconds and seconds % 3600 == 0:
        return f"{seconds // 3600} ч"
    return f"{max(seconds, 60) // 60} мин"


def _country_name(code: str) -> str:
    country = COUNTRY_BY_CODE.get(code)
    return country.name if country else code


async def _render(session: AsyncSession, status: TravelStatus):
    city = await get_city(session, status.city_id)
    h = status.holdings
    if status.emperor:
        rules = RULES_EMPEROR
    elif status.must_abandon:
        rules = RULES_GANG_DISTRICTS
    elif status.phase == PHASE_CIRCLE:
        rules = RULES_CIRCLE.format(interval=interval_label(status.interval_seconds))
    else:
        rules = RULES_GANG.format(interval=interval_label(status.interval_seconds))
    text = TRAVEL_SCREEN.format(
        country=_country_name(status.country_code),
        city=city.name if city else "—",
        districts=format_number(h.districts),
        holdings_tail=HOLDINGS_TAIL.format(cities=h.cities, buildings=format_number(h.buildings)) if h.districts else "",
        rules=rules,
        cooldown=COOLDOWN_LINE.format(countdown=format_countdown(status.cooldown_seconds))
        if status.cooldown_seconds and not status.emperor
        else "",
    )
    if status.city_interval_seconds and not status.must_abandon:
        text += RULES_INTERVAL_LINE.format(interval=interval_label(status.city_interval_seconds))
    if status.city_cooldown_seconds:
        text += CITY_COOLDOWN_LINE.format(countdown=format_countdown(status.city_cooldown_seconds))
    if status.under_challenge:
        text += CHALLENGE_LINE
    return text, travel_menu(status.country_code, must_abandon=status.must_abandon, can_leave_country=not status.emperor)


_ALERTS = {
    NotOnboardedError: NOT_ONBOARDED_ALERT,
    SameCityError: SAME_CITY_ALERT,
    HasDistrictsError: HAS_DISTRICTS_ALERT,
    NoDistrictsError: NO_DISTRICTS_ALERT,
    EmperorCannotLeaveError: EMPEROR_ALERT,
    UnknownCityError: UNKNOWN_CITY_ALERT,
    CountryEntryClosedError: COUNTRY_CLOSED_ALERT,
    ChallengePendingError: CHALLENGE_PENDING_ALERT,
}


async def _alert(callback: CallbackQuery, exc: Exception) -> None:
    if isinstance(exc, CountrySwapCooldownError):
        await callback.answer(COOLDOWN_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
    elif isinstance(exc, CityMoveCooldownError):
        await callback.answer(CITY_COOLDOWN_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
    else:
        await callback.answer(_ALERTS[type(exc)], show_alert=True)


_HANDLED = (*_ALERTS, CountrySwapCooldownError, CityMoveCooldownError)


@router.callback_query(F.data == CB_TRAVEL_OPEN)
async def cb_travel_open(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        status = await get_status(session, redis, callback.from_user.id)
    except NotOnboardedError as e:
        await _alert(callback, e)
        return
    await callback.answer()
    text, markup = await _render(session, status)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_TRAVEL_COUNTRIES)
async def cb_travel_countries(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        status = await get_status(session, redis, callback.from_user.id)
        if status.emperor:
            raise EmperorCannotLeaveError
        if status.must_abandon:
            raise HasDistrictsError
        if status.under_challenge:
            raise ChallengePendingError
    except _HANDLED as e:
        await _alert(callback, e)
        return
    await callback.answer()
    exclude = set(await closed_entries(session)) | {status.country_code}
    await safe_edit_text(callback.message, PICK_COUNTRY, reply_markup=countries_menu(exclude))


@router.callback_query(F.data.startswith(CB_TRAVEL_CITIES_PREFIX))
async def cb_travel_cities(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    code, _, raw_page = callback.data.removeprefix(CB_TRAVEL_CITIES_PREFIX).partition(":")
    if code not in COUNTRY_BY_CODE:
        await callback.answer()
        return
    try:
        status = await get_status(session, redis, callback.from_user.id)
    except NotOnboardedError as e:
        await _alert(callback, e)
        return
    cities = [c for c in await list_cities(session, code) if c.id != status.city_id]
    await callback.answer()
    await safe_edit_text(
        callback.message,
        PICK_CITY.format(country=_country_name(code)),
        reply_markup=cities_menu(code, cities, int(raw_page) if raw_page.isdigit() else 0, own_country=code == status.country_code),
    )


async def _moved(callback: CallbackQuery, result) -> None:
    text = MOVED.format(country=_country_name(result.city.country_code), city=result.city.name)
    if result.lost:
        text += MOVED_LOST.format(districts=format_number(result.lost.districts), buildings=format_number(result.lost.buildings))
    await safe_edit_text(callback.message, text, reply_markup=after_move_menu())


@router.callback_query(F.data.startswith(CB_TRAVEL_PICK_PREFIX))
async def cb_travel_pick(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    raw = callback.data.removeprefix(CB_TRAVEL_PICK_PREFIX)
    city = await get_city(session, int(raw)) if raw.isdigit() else None
    try:
        if city is None:
            raise UnknownCityError
        status = await get_status(session, redis, callback.from_user.id)
        await check_move(session, redis, status, city)
        if city.country_code == status.country_code:  # своя страна — без подтверждения, переезд обратно бесплатный
            result = await move(session, redis, callback.from_user.id, city.id)
            await callback.answer()
            await _moved(callback, result)
            return
    except _HANDLED as e:
        await _alert(callback, e)
        return
    h = status.holdings
    losses = (
        CONFIRM_LOSSES.format(districts=format_number(h.districts), cities=h.cities, buildings=format_number(h.buildings))
        if h.districts
        else ""
    )
    await callback.answer()
    await safe_edit_text(
        callback.message,
        CONFIRM_COUNTRY.format(
            country=_country_name(city.country_code), city=city.name,
            interval=interval_label(status.interval_seconds), losses=losses,
        ),
        reply_markup=confirm_menu(city.id),
    )


@router.callback_query(F.data.startswith(CB_TRAVEL_GO_PREFIX))
async def cb_travel_go(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    raw = callback.data.removeprefix(CB_TRAVEL_GO_PREFIX)
    try:
        if not raw.isdigit():
            raise UnknownCityError
        # Подтверждение потерь — сам экран, с которого нажата кнопка.
        result = await move(session, redis, callback.from_user.id, int(raw), accept_losses=True)
    except LossesNotConfirmedError:
        await callback.answer()
        return
    except _HANDLED as e:
        await _alert(callback, e)
        return
    await callback.answer()
    await _moved(callback, result)


@router.callback_query(F.data == CB_TRAVEL_ABANDON_ASK)
async def cb_travel_abandon_ask(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        status = await get_status(session, redis, callback.from_user.id)
        if not status.must_abandon:
            raise NoDistrictsError
        if status.under_challenge:
            raise ChallengePendingError
    except _HANDLED as e:
        await _alert(callback, e)
        return
    await callback.answer()
    h = status.holdings
    await safe_edit_text(
        callback.message,
        ABANDON_ASK.format(districts=format_number(h.districts), buildings=format_number(h.buildings)),
        reply_markup=abandon_menu(),
    )


@router.callback_query(F.data == CB_TRAVEL_ABANDON)
async def cb_travel_abandon(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        lost = await abandon_districts(session, callback.from_user.id)
    except _HANDLED as e:
        await _alert(callback, e)
        return
    await callback.answer(
        ABANDONED.format(districts=format_number(lost.districts), buildings=format_number(lost.buildings)), show_alert=True
    )
    status = await get_status(session, redis, callback.from_user.id)
    text, markup = await _render(session, status)
    await safe_edit_text(callback.message, text, reply_markup=markup)
