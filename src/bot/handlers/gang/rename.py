"""Смена названия банды (пользователь 2026-11-12): 10 млн NHCoin, раз в неделю (хендлеры)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.common import CB_MENU_SETTINGS
from bot.constant.gang import CB_GANG_RENAME
from bot.services.gang import InvalidGangNameError, get_gang
from bot.services.gang.rename import RenameCooldownError, RenameNotEnoughError, rename_gang, rename_cooldown
from bot.states.gang import GangStates
from bot.texts.gang import NAME_TOO_LONG, NAME_TOO_SHORT
from bot.texts.gang.rename import COOLDOWN, DONE, NOT_ENOUGH, PROMPT
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.settings import BTN_BACK_TO_SETTINGS
from bot.config.game import GANG_RENAME_COOLDOWN_DAYS, GANG_RENAME_PRICE
from bot.utils.formatting import esc, format_countdown, format_number

router = Router(name="gang_rename")


def _back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_BACK_TO_SETTINGS, callback_data=CB_MENU_SETTINGS)]])


@router.callback_query(F.data == CB_GANG_RENAME)
async def cb_rename(callback: CallbackQuery, session: AsyncSession, redis: Redis, state: FSMContext) -> None:
    gang = await get_gang(session, callback.from_user.id)
    if gang is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    left = await rename_cooldown(redis, callback.from_user.id)
    if left:
        await callback.message.answer(COOLDOWN.format(left=format_countdown(left)), reply_markup=_back())
        return
    await state.set_state(GangStates.waiting_rename)
    await callback.message.answer(
        PROMPT.format(name=esc(gang.name), price=format_number(GANG_RENAME_PRICE), days=GANG_RENAME_COOLDOWN_DAYS),
        reply_markup=_back(),
    )


@router.message(GangStates.waiting_rename, F.text)
async def msg_rename(message: Message, session: AsyncSession, redis: Redis, state: FSMContext) -> None:
    try:
        name = await rename_gang(session, redis, message.from_user.id, message.text)
    except InvalidGangNameError as exc:
        await message.answer(NAME_TOO_SHORT if str(exc) == "too_short" else NAME_TOO_LONG, reply_markup=_back())
        return
    except RenameCooldownError as exc:
        await state.clear()
        await message.answer(COOLDOWN.format(left=format_countdown(exc.seconds)), reply_markup=_back())
        return
    except RenameNotEnoughError:
        await state.clear()
        await message.answer(NOT_ENOUGH.format(price=format_number(GANG_RENAME_PRICE)), reply_markup=_back())
        return
    await state.clear()
    await message.answer(DONE.format(name=esc(name), price=format_number(GANG_RENAME_PRICE)), reply_markup=_back())
