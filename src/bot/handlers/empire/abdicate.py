"""Сложить империю: экран, выбор страны, подтверждение (хендлеры). Логика — `services/empire/abdicate`."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.empire import EMPIRE_ABDICATE_COOLDOWN_DAYS, EMPIRE_ABDICATE_FINE_PERCENT, EMPIRE_ABDICATE_MAX_CITIES
from bot.constant.empire import CB_EMPIRE_ABDICATE, CB_EMPIRE_ABDICATE_TO_PREFIX, CB_EMPIRE_ABDICATE_YES_PREFIX, CB_EMPIRE_OPEN
from bot.config.country import COUNTRY_BY_CODE
from bot.db.repositories.user import get_by_id
from bot.services.empire import abdicate as svc
from bot.texts.empire import BTN_BACK_TO_EMPIRE
from bot.texts.empire import abdicate as t
from bot.utils.formatting import format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="empire_abdicate")


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _back() -> list[InlineKeyboardButton]:
    return [_btn(BTN_BACK_TO_EMPIRE, CB_EMPIRE_OPEN)]


@router.callback_query(F.data == CB_EMPIRE_ABDICATE)
async def cb_abdicate(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user = await get_by_id(session, callback.from_user.id)
    if user is None:
        await callback.answer()
        return
    view = await svc.get_view(session, redis, user)
    text = t.SCREEN.format(
        cities=view.cities, max_cities=EMPIRE_ABDICATE_MAX_CITIES, fine=format_number(view.fine),
        fine_percent=EMPIRE_ABDICATE_FINE_PERCENT, cd_days=EMPIRE_ABDICATE_COOLDOWN_DAYS,
    )
    rows = []
    if not view.allowed:
        text += t.NOT_ALLOWED.format(max_cities=EMPIRE_ABDICATE_MAX_CITIES)
    elif view.cooldown_seconds:
        text += t.COOLDOWN.format(left=format_countdown(view.cooldown_seconds))
    else:
        text += t.PICK
        buttons = [_btn(name, f"{CB_EMPIRE_ABDICATE_TO_PREFIX}{code}") for code, name in view.countries]
        rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    await callback.answer()
    await safe_edit_text(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[*rows, _back()]))


@router.callback_query(F.data.startswith(CB_EMPIRE_ABDICATE_TO_PREFIX))
async def cb_pick(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    code = callback.data.removeprefix(CB_EMPIRE_ABDICATE_TO_PREFIX)
    country = COUNTRY_BY_CODE.get(code)
    user = await get_by_id(session, callback.from_user.id)
    if country is None or user is None:
        await callback.answer()
        return
    view = await svc.get_view(session, redis, user)
    await callback.answer()
    await safe_edit_text(
        callback.message,
        t.CONFIRM.format(country=country.name, cities=view.cities, fine=format_number(view.fine), cd_days=EMPIRE_ABDICATE_COOLDOWN_DAYS),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn(t.BTN_YES, f"{CB_EMPIRE_ABDICATE_YES_PREFIX}{code}")],
            [_btn(t.BTN_NO, CB_EMPIRE_ABDICATE)],
        ]),
    )


@router.callback_query(F.data.startswith(CB_EMPIRE_ABDICATE_YES_PREFIX))
async def cb_yes(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    code = callback.data.removeprefix(CB_EMPIRE_ABDICATE_YES_PREFIX)
    try:
        done = await svc.abdicate(session, redis, callback.from_user.id, code)
    except svc.NotEmperorError:
        await callback.answer(t.NOT_EMPEROR_ALERT, show_alert=True)
        return
    except svc.TooManyCitiesError:
        await callback.answer(t.TOO_MANY_ALERT.format(max_cities=EMPIRE_ABDICATE_MAX_CITIES), show_alert=True)
        return
    except svc.AbdicateCooldownError as exc:
        await callback.answer(t.COOLDOWN_ALERT.format(left=format_countdown(exc.seconds)), show_alert=True)
        return
    except svc.AtWarError:
        await callback.answer(t.AT_WAR_ALERT, show_alert=True)
        return
    except svc.BadCountryError:
        await callback.answer(t.BAD_COUNTRY_ALERT, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message,
        t.DONE.format(cities=done.cities_lost, country=done.country_name, city=done.city_name, fine=format_number(done.fine)),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[]),
    )
