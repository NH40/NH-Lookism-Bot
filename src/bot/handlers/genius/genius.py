"""Гениальность — список, уровни, свап, прокачка, прокрут (хендлеры).

Вход — «🧠 Гениальность» на экране «📈 Развитие» и прокрут в «🛍 Магазине».
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.genius import LEVELS
from bot.constant.genius import (
    CB_GENIUS_ACTIVATE_PREFIX,
    CB_GENIUS_LEVEL_UP_PREFIX,
    CB_GENIUS_OPEN,
    CB_GENIUS_ROLL,
    CB_GENIUS_VIEW_PREFIX,
    GENIUSES,
)
from bot.keyboards.genius import genius_detail_menu, genius_menu
from bot.services.gang import get_gang
from bot.services.genius import (
    GeniusBusyError,
    GeniusMaxLevelError,
    GeniusNotOwnedError,
    NotEnoughFragmentsError,
    SwapOnCooldownError,
    UnknownGeniusError,
    activate,
    ensure_genius,
    get_view,
    level_up,
    roll,
)
from bot.texts.development import describe_level
from bot.texts.genius import (
    ACTIVATED_ALERT,
    BUSY_ALERT,
    DETAIL_ACTIVE,
    GENIUS_DETAIL,
    GENIUS_NAMES,
    GENIUS_SCREEN,
    GENIUS_THEMES,
    LEVEL_LINE_DONE,
    LEVEL_LINE_LOCKED,
    LEVEL_UP_ALERT,
    MARK_ACTIVE,
    MARK_OWNED,
    MAX_LEVEL_ALERT,
    MAX_LEVEL_LINE,
    NEXT_LEVEL_LINE,
    NOT_ENOUGH_ALERT,
    NOT_ENOUGH_ROLL_ALERT,
    NOT_OWNED_ALERT,
    OWNED_LINE,
    ROLL_DUPLICATE,
    ROLL_NEW,
    SWAP_COOLDOWN_ALERT,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.formatting import format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="genius")


async def render_genius(session: AsyncSession, redis: Redis, user_id: int):
    await ensure_genius(session, user_id)
    view = await get_view(session, redis, user_id)
    owned = "\n".join(
        OWNED_LINE.format(mark=MARK_ACTIVE if code == view.active else MARK_OWNED, name=GENIUS_NAMES[code], level=level)
        for code, level in view.owned.items()
    )
    text = GENIUS_SCREEN.format(
        active=GENIUS_NAMES.get(view.active, "—"), fragments=format_number(view.fragments), owned=owned or "—"
    )
    return text, genius_menu(view.owned, view.active)


async def _render_detail(session: AsyncSession, redis: Redis, user_id: int, code: str):
    view = await get_view(session, redis, user_id)
    level = view.owned[code]
    levels = "\n".join(
        (LEVEL_LINE_DONE if n <= level else LEVEL_LINE_LOCKED).format(n=n, effect=describe_level(spec))
        for n, spec in enumerate(LEVELS[code], 1)
    )
    cost = view.next_costs[code]
    text = GENIUS_DETAIL.format(
        name=GENIUS_NAMES[code],
        level=level,
        active=DETAIL_ACTIVE if code == view.active else "",
        theme=GENIUS_THEMES[code],
        levels=levels,
        next_line=NEXT_LEVEL_LINE.format(cost=format_number(cost), have=format_number(view.fragments))
        if cost is not None
        else MAX_LEVEL_LINE,
    )
    return text, genius_detail_menu(code, cost=cost, is_active=code == view.active)


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


@router.callback_query(F.data == CB_GENIUS_OPEN)
async def cb_genius_open(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    text, markup = await render_genius(session, redis, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_GENIUS_VIEW_PREFIX))
async def cb_genius_view(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    code = callback.data.removeprefix(CB_GENIUS_VIEW_PREFIX)
    view = await get_view(session, redis, callback.from_user.id)
    if code not in GENIUSES or code not in view.owned:
        await callback.answer(NOT_OWNED_ALERT, show_alert=True)
        return
    await callback.answer()
    text, markup = await _render_detail(session, redis, callback.from_user.id, code)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_GENIUS_ACTIVATE_PREFIX))
async def cb_genius_activate(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    code = callback.data.removeprefix(CB_GENIUS_ACTIVATE_PREFIX)
    # Popup-тексты — без HTML.
    try:
        await activate(session, redis, callback.from_user.id, code)
    except (UnknownGeniusError, GeniusNotOwnedError):
        await callback.answer(NOT_OWNED_ALERT, show_alert=True)
        return
    except SwapOnCooldownError as exc:
        await callback.answer(SWAP_COOLDOWN_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
        return
    await callback.answer(ACTIVATED_ALERT.format(name=GENIUS_NAMES[code]))
    text, markup = await _render_detail(session, redis, callback.from_user.id, code)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_GENIUS_LEVEL_UP_PREFIX))
async def cb_genius_level_up(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    code = callback.data.removeprefix(CB_GENIUS_LEVEL_UP_PREFIX)
    try:
        level = await level_up(session, callback.from_user.id, code)
    except GeniusNotOwnedError:
        await callback.answer(NOT_OWNED_ALERT, show_alert=True)
        return
    except GeniusMaxLevelError:
        await callback.answer(MAX_LEVEL_ALERT, show_alert=True)
        return
    except NotEnoughFragmentsError as exc:
        await callback.answer(NOT_ENOUGH_ALERT.format(cost=exc.cost, have=exc.have), show_alert=True)
        return
    await callback.answer(LEVEL_UP_ALERT.format(name=GENIUS_NAMES[code], level=level))
    text, markup = await _render_detail(session, redis, callback.from_user.id, code)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_GENIUS_ROLL)
async def cb_genius_roll(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    try:
        result = await roll(session, redis, callback.from_user.id)
    except GeniusBusyError:
        await callback.answer(BUSY_ALERT)
        return
    except NotEnoughFragmentsError:
        await callback.answer(NOT_ENOUGH_ROLL_ALERT, show_alert=True)
        return
    await callback.answer()
    template = ROLL_DUPLICATE if result.duplicate else ROLL_NEW
    await callback.message.answer(template.format(name=GENIUS_NAMES[result.code]))
    text, markup = await render_genius(session, redis, callback.from_user.id)
    await callback.message.answer(text, reply_markup=markup)
