"""Саботаж против императора — экран и три действия (хендлеры).

Вход — «🕵️ Саботаж» в профиле (видна подданным чужого императора). Императору — анонимный
пуш об удаче или провале; имя саботажника нигде не показывается (раскрытие — будущий навык
Шпиона, см. `services/empire/sabotage.py`).
"""
from __future__ import annotations

from bot.keyboards.common import back_menu

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.card import CARD_BY_CODE
from bot.constant.empire import CB_SABOTAGE_DO_PREFIX, CB_SABOTAGE_MARKED_PREFIX, CB_SABOTAGE_OPEN
from bot.keyboards.empire import sabotage_menu
from bot.services.empire import (
    NoEmperorError,
    NotMarkedTargetError,
    NothingToStealError,
    SabotageOnCooldownError,
    SabotageResult,
    UnknownSabotageError,
    get_sabotage_view,
    sabotage,
)
from bot.services.gang import get_gang
from bot.texts.empire import (
    NO_EMPEROR,
    NOT_MARKED_ALERT,
    NOTHING_TO_STEAL_ALERT,
    PUSH_SABOTAGE_FAIL,
    PUSH_SABOTAGE_SUCCESS,
    SABOTAGE_COOLDOWN_ALERT,
    SABOTAGE_FAIL,
    SABOTAGE_READY_LINE,
    SABOTAGE_SCREEN,
    SABOTAGE_SUCCESS,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.formatting import esc, format_countdown, format_number
from bot.services.settings import notify_player
from bot.constant.settings import NOTIFY_SABOTAGE
from bot.utils.safe_edit import safe_edit_text

router = Router(name="empire_sabotage")


async def _render(session: AsyncSession, redis: Redis, user_id: int):
    view = await get_sabotage_view(session, redis, user_id)
    emperor = view.emperor
    text = SABOTAGE_SCREEN.format(
        emperor=f"@{esc(emperor.emperor_username)}" if emperor.emperor_username else esc(emperor.emperor_name or "—"),
        percent=emperor.percent,
        cooldown_line=SABOTAGE_READY_LINE,
    )
    return text, sabotage_menu({a: format_countdown(s) if s else None for a, s in view.cooldowns.items()})


def _fields(result: SabotageResult) -> dict:
    card = CARD_BY_CODE.get(result.card_code) if result.card_code else None
    return {
        "amount": format_number(result.amount),
        "rank": result.rank or "",
        "card": esc(card.name) if card else (result.card_code or ""),
    }


@router.callback_query(F.data == CB_SABOTAGE_OPEN)
async def cb_sabotage_open(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        text, markup = await _render(session, redis, callback.from_user.id)
    except NoEmperorError:
        await callback.answer(NO_EMPEROR, show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_SABOTAGE_MARKED_PREFIX))
async def cb_sabotage_marked(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    """Саботаж помеченного игрока (путь Сенсорики) — те же действия и КД, цель — метка."""
    user_id = callback.from_user.id
    try:
        action, raw_target = callback.data.removeprefix(CB_SABOTAGE_MARKED_PREFIX).split(":", 1)
        target_id = int(raw_target)
    except ValueError:
        await callback.answer()
        return
    try:
        result = await sabotage(session, redis, user_id, action, target_id=target_id)
    except (UnknownSabotageError, NotMarkedTargetError):
        await callback.answer(NOT_MARKED_ALERT, show_alert=True)
        return
    except NothingToStealError:
        await callback.answer(NOTHING_TO_STEAL_ALERT, show_alert=True)
        return
    except SabotageOnCooldownError as exc:
        await callback.answer(
            SABOTAGE_COOLDOWN_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True
        )
        return
    await callback.answer()
    fields = _fields(result)
    await callback.message.answer(SABOTAGE_SUCCESS[result.action].format(**fields) if result.success else SABOTAGE_FAIL, reply_markup=back_menu(CB_SABOTAGE_OPEN))
    if not result.silent:
        push = PUSH_SABOTAGE_SUCCESS[result.action].format(**fields) if result.success else PUSH_SABOTAGE_FAIL
        await notify_player(callback.bot, session, result.emperor_id, NOTIFY_SABOTAGE, push)


@router.callback_query(F.data.startswith(CB_SABOTAGE_DO_PREFIX))
async def cb_sabotage_do(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user_id = callback.from_user.id
    if await get_gang(session, user_id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    action = callback.data.removeprefix(CB_SABOTAGE_DO_PREFIX)
    # Popup-тексты — без HTML.
    try:
        result = await sabotage(session, redis, user_id, action)
    except UnknownSabotageError:
        await callback.answer()
        return
    except NoEmperorError:
        await callback.answer(NO_EMPEROR, show_alert=True)
        return
    except NothingToStealError:
        await callback.answer(NOTHING_TO_STEAL_ALERT, show_alert=True)
        return
    except SabotageOnCooldownError as exc:
        await callback.answer(
            SABOTAGE_COOLDOWN_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True
        )
        return
    await callback.answer()
    fields = _fields(result)
    if result.success:
        await callback.message.answer(SABOTAGE_SUCCESS[result.action].format(**fields), reply_markup=back_menu(CB_SABOTAGE_OPEN))
    else:
        await callback.message.answer(SABOTAGE_FAIL, reply_markup=back_menu(CB_SABOTAGE_OPEN))
    # Курода: «тихий» саботаж — император не узнаёт даже о попытке.
    if not result.silent:
        push = PUSH_SABOTAGE_SUCCESS[result.action].format(**fields) if result.success else PUSH_SABOTAGE_FAIL
        await notify_player(callback.bot, session, result.emperor_id, NOTIFY_SABOTAGE, push)
    # Экран обновляется — кнопки сменяются таймером КД.
    text, markup = await _render(session, redis, user_id)
    await safe_edit_text(callback.message, text, reply_markup=markup)
