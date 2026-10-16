"""Battle Pass (хендлеры). Вход — «🎫 Battle Pass» на экране заданий."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.battle_pass import BP_LEVEL_XP, loop_position
from bot.services.admin.live_config import get as live_get
from bot.constant.battle_pass import (
    CB_BP_CLAIM_ALL_PREFIX,
    CB_BP_CLAIM_PREFIX,
    CB_BP_BUY_PREMIUM,
    CB_BP_OPEN,
    CB_BP_PAGE_PREFIX,
    TRACKS,
)
from bot.keyboards.battle_pass import pass_menu
from bot.services.battle_pass import (
    AlreadyPremiumError,
    BattlePassBusyError,
    NotEnoughDonateError,
    buy_premium,
    LevelAlreadyClaimedError,
    LevelLockedError,
    NothingToClaimError,
    NotPremiumError,
    claim_all,
    claim_level,
    get_page,
    page_for_level,
)
from bot.services.gang import get_gang
from bot.texts.battle_pass import (
    ALREADY_ALERT,
    BOOST_OFF,
    BOOST_ON,
    BUSY_ALERT,
    CLAIMED_ALERT,
    CLAIMED_ALL_ALERT,
    LEVEL_ROW,
    LOCKED_ALERT,
    LOOP_NOTE,
    MARK_CLAIMED,
    MARK_LOCKED,
    MARK_READY,
    NOTHING_ALERT,
    NOT_PREMIUM_ALERT,
    PASS_HEADER,
    PREMIUM_ALREADY_ALERT,
    PREMIUM_BOUGHT_ALERT,
    PREMIUM_NOT_ENOUGH_ALERT,
    PREMIUM_OFF,
    PREMIUM_ON,
    SEPARATOR,
    STAR_CURRENT,
    reward_text,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.formatting import emoji_bar, format_duration
from bot.utils.safe_edit import safe_edit_text

router = Router(name="battle_pass")

_ERROR_ALERTS = {
    LevelLockedError: LOCKED_ALERT,
    LevelAlreadyClaimedError: ALREADY_ALERT,
    NotPremiumError: NOT_PREMIUM_ALERT,
    NothingToClaimError: NOTHING_ALERT,
}


def _mark(claimed: bool, open_: bool) -> str:
    return MARK_CLAIMED if claimed else (MARK_READY if open_ else MARK_LOCKED)


async def render_pass(session: AsyncSession, user_id: int, page: int | None = None):
    p = await get_page(session, user_id, page)
    rows = "\n".join(
        LEVEL_ROW.format(
            level=e.level, star=STAR_CURRENT if e.level == p.level else "",
            free_mark=_mark(e.free_claimed, e.level <= p.level), free=reward_text(e.free),
            premium_mark=_mark(e.premium_claimed, e.level <= p.level and p.is_premium), premium=reward_text(e.premium),
        )
        for e in p.entries
    )
    percent = p.xp_in_level * 100 // BP_LEVEL_XP
    pos = loop_position(p.level)
    boost_reset = format_duration(p.boost.resets_in)
    boost = (
        BOOST_ON.format(mult=p.boost.multiplier, used=p.boost.used, cap=p.boost.cap, reset=boost_reset)
        if p.boost.multiplier > 1 else BOOST_OFF.format(reset=boost_reset)
    )
    text = PASS_HEADER.format(
        season=p.season_number, season_left=format_duration(p.season_left), sep=SEPARATOR, level=p.level,
        loop=LOOP_NOTE.format(pos=pos) if pos else "", bar=emoji_bar(percent, fill="🟨"), percent=percent,
        xp=p.xp_in_level, level_xp=BP_LEVEL_XP, boost=boost, premium=PREMIUM_ON if p.is_premium else PREMIUM_OFF.format(price=live_get("bp_premium_price")),
        scrolls=p.scrolls, low=p.entries[0].level, high=p.entries[-1].level, rows=rows,
    )
    await session.commit()  # сезон мог открыться только что (ленивое создание)
    return text, pass_menu(p)


async def _show(callback: CallbackQuery, session: AsyncSession, page: int | None = None) -> None:
    text, markup = await render_pass(session, callback.from_user.id, page)
    await safe_edit_text(callback.message, text, reply_markup=markup)


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


@router.callback_query(F.data == CB_BP_OPEN)
async def cb_open(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    await _show(callback, session)


@router.callback_query(F.data.startswith(CB_BP_PAGE_PREFIX))
async def cb_page(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_BP_PAGE_PREFIX)
    if not raw.isdigit() or not await _guard(callback, session):
        await callback.answer()
        return
    await callback.answer()
    await _show(callback, session, int(raw))


@router.callback_query(F.data.startswith(CB_BP_CLAIM_PREFIX))
async def cb_claim(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    track, _, raw = callback.data.removeprefix(CB_BP_CLAIM_PREFIX).partition(":")
    if track not in TRACKS or not raw.isdigit() or not await _guard(callback, session):
        await callback.answer()
        return
    level = int(raw)
    try:
        result = await claim_level(session, redis, callback.from_user.id, track, level)
    except BattlePassBusyError:
        await callback.answer(BUSY_ALERT)
        return
    except tuple(_ERROR_ALERTS) as exc:
        await callback.answer(_ERROR_ALERTS[type(exc)], show_alert=True)
        return
    # Popup — без HTML.
    await callback.answer(CLAIMED_ALERT.format(reward=reward_text(result.reward)), show_alert=True)
    await _show(callback, session, page_for_level(level))


@router.callback_query(F.data.startswith(CB_BP_CLAIM_ALL_PREFIX))
async def cb_claim_all(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    track = callback.data.removeprefix(CB_BP_CLAIM_ALL_PREFIX)
    if track not in TRACKS or not await _guard(callback, session):
        await callback.answer()
        return
    try:
        result = await claim_all(session, redis, callback.from_user.id, track)
    except BattlePassBusyError:
        await callback.answer(BUSY_ALERT)
        return
    except tuple(_ERROR_ALERTS) as exc:
        await callback.answer(_ERROR_ALERTS[type(exc)], show_alert=True)
        return
    await callback.answer(CLAIMED_ALL_ALERT.format(count=result.count, reward=reward_text(result.reward)), show_alert=True)
    await _show(callback, session, page_for_level(result.level))


@router.callback_query(F.data == CB_BP_BUY_PREMIUM)
async def cb_buy_premium(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    try:
        await buy_premium(session, redis, callback.from_user.id)
    except BattlePassBusyError:
        await callback.answer(BUSY_ALERT)
        return
    except AlreadyPremiumError:
        await callback.answer(PREMIUM_ALREADY_ALERT, show_alert=True)
        return
    except NotEnoughDonateError as exc:
        await callback.answer(PREMIUM_NOT_ENOUGH_ALERT.format(price=exc.price, balance=exc.balance), show_alert=True)
        return
    await callback.answer(PREMIUM_BOUGHT_ALERT, show_alert=True)
    await _show(callback, session)
