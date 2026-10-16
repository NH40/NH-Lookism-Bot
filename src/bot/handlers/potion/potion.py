"""Зелья (хендлеры): каталог, тиры вида, выпить, авто-зелья. Вход — «🧪 Зелья» в магазине.
`send_auto_pushes()` — публичная функция домена для фонового прохода авто-зелий (`main.py`)."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.potion import CB_POTION_AUTO_PREFIX, CB_POTION_BUY_PREFIX, CB_POTION_KIND_PREFIX, CB_POTION_OPEN, POTIONS
from bot.constant.settings import NOTIFY_POTION
from bot.keyboards.potion import kind_menu, potions_menu
from bot.services.gang import get_gang
from bot.services.potion import (
    AutoSlotsFullError,
    NotEnoughCoinsError,
    PotionBusyError,
    TierLockedError,
    UnknownPotionError,
    buy,
    catalog,
    offers,
    set_auto,
)
from bot.services.settings import notify_player
from bot.texts.development import describe_level
from bot.texts.potion import (
    ACTIVE_HEAD,
    ACTIVE_LINE,
    ACTIVE_NONE,
    AUTO_FULL_ALERT,
    AUTO_MARK,
    AUTO_NO_SLOTS_ALERT,
    AUTO_OFF_ALERT,
    AUTO_ON_ALERT,
    AUTO_REASON_COINS,
    AUTO_REASON_LOCKED,
    BUSY_ALERT,
    DRANK_ALERT,
    KIND_AUTO,
    KIND_POWER,
    KIND_SCREEN,
    KIND_STATE,
    LOCKED_ALERT,
    MEDICINE_EXTRA_AUTO,
    MEDICINE_EXTRA_DISCOUNT,
    MEDICINE_EXTRA_DURATION,
    MEDICINE_EXTRA_POWER,
    MEDICINE_LINE,
    MEDICINE_NONE,
    NOT_ENOUGH_ALERT,
    POTION_ABOUT,
    POTION_NAMES,
    POTION_SCREEN,
    PUSH_AUTO_STOPPED,
    ROMAN,
    TIER_LINE,
    TIER_LINE_LOCKED,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.formatting import format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="potion")


def _pct(value: float) -> str:
    return f"{round(value * 100):g}%"


async def render_potions(session: AsyncSession, user_id: int):
    cat = await catalog(session, user_id)
    if cat.max_tier > 2 or cat.discount or cat.auto_slots:
        extras = (
            (MEDICINE_EXTRA_DISCOUNT.format(p=_pct(cat.discount)) if cat.discount else "")
            + (MEDICINE_EXTRA_DURATION.format(p=_pct(cat.duration)) if cat.duration else "")
            + (MEDICINE_EXTRA_POWER.format(p=_pct(cat.power)) if cat.power else "")
            + (MEDICINE_EXTRA_AUTO.format(n=cat.auto_slots) if cat.auto_slots else "")
        )
        medicine = MEDICINE_LINE.format(roman=ROMAN[cat.max_tier], extras=extras)
    else:
        medicine = MEDICINE_NONE
    active = [s for s in cat.states.values() if s.tier]
    lines = (
        ACTIVE_HEAD
        + "".join(
            ACTIVE_LINE.format(
                name=POTION_NAMES[s.kind], roman=ROMAN[s.tier], countdown=format_countdown(s.left_seconds),
                auto=AUTO_MARK if s.auto_tier else "",
            )
            for s in sorted(active, key=lambda s: POTIONS.index(s.kind))
        )
        if active
        else ACTIVE_NONE
    )
    return POTION_SCREEN.format(medicine=medicine, active=lines), potions_menu(cat.states)


async def render_kind(session: AsyncSession, user_id: int, kind: str):
    cat = await catalog(session, user_id)
    tiers = await offers(session, user_id, kind)
    state = cat.states.get(kind)
    text_tiers = "".join(
        (TIER_LINE if o.unlocked else TIER_LINE_LOCKED).format(
            roman=ROMAN[o.tier], price=format_number(o.price), effect=describe_level(o.spec)
        )
        for o in tiers
    )
    status = ""
    if state and state.tier:
        status += KIND_STATE.format(roman=ROMAN[state.tier], countdown=format_countdown(state.left_seconds))
    if state and state.auto_tier:
        status += KIND_AUTO.format(roman=ROMAN[state.auto_tier])
    text = KIND_SCREEN.format(
        name=f"<b>{POTION_NAMES[kind]}</b>", about=POTION_ABOUT[kind], minutes=tiers[0].minutes,
        power=KIND_POWER.format(p=_pct(cat.power)) if cat.power else "", tiers=text_tiers, state=status,
    )
    return text, kind_menu(kind, tiers, cat.auto_slots, state.auto_tier if state else 0)


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


def _kind_tier(raw: str) -> tuple[str, int] | None:
    kind, _, tier = raw.rpartition(":")
    return (kind, int(tier)) if tier.isdigit() and kind in POTIONS else None


@router.callback_query(F.data == CB_POTION_OPEN)
async def cb_potion_open(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    text, markup = await render_potions(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_POTION_KIND_PREFIX))
async def cb_potion_kind(callback: CallbackQuery, session: AsyncSession) -> None:
    kind = callback.data.removeprefix(CB_POTION_KIND_PREFIX)
    if kind not in POTIONS or not await _guard(callback, session):
        await callback.answer()
        return
    await callback.answer()
    text, markup = await render_kind(session, callback.from_user.id, kind)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_POTION_BUY_PREFIX))
async def cb_potion_buy(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    parsed = _kind_tier(callback.data.removeprefix(CB_POTION_BUY_PREFIX))
    if parsed is None or not await _guard(callback, session):
        await callback.answer()
        return
    kind, tier = parsed
    # Popup-тексты — без HTML.
    try:
        offer = await buy(session, redis, callback.from_user.id, kind, tier)
    except PotionBusyError:
        await callback.answer(BUSY_ALERT)
        return
    except UnknownPotionError:
        await callback.answer()
        return
    except TierLockedError as exc:
        await callback.answer(LOCKED_ALERT.format(roman=ROMAN[exc.max_tier]), show_alert=True)
        return
    except NotEnoughCoinsError as exc:
        await callback.answer(NOT_ENOUGH_ALERT.format(cost=format_number(exc.cost)), show_alert=True)
        return
    await callback.answer(DRANK_ALERT.format(name=POTION_NAMES[kind], roman=ROMAN[tier], minutes=offer.minutes))
    text, markup = await render_kind(session, callback.from_user.id, kind)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_POTION_AUTO_PREFIX))
async def cb_potion_auto(callback: CallbackQuery, session: AsyncSession) -> None:
    parsed = _kind_tier(callback.data.removeprefix(CB_POTION_AUTO_PREFIX))
    if parsed is None or not await _guard(callback, session):
        await callback.answer()
        return
    kind, tier = parsed
    try:
        await set_auto(session, callback.from_user.id, kind, tier)
    except (UnknownPotionError, TierLockedError):
        await callback.answer()
        return
    except AutoSlotsFullError as exc:
        await callback.answer(AUTO_FULL_ALERT.format(slots=exc.slots) if exc.slots else AUTO_NO_SLOTS_ALERT, show_alert=True)
        return
    await callback.answer(AUTO_ON_ALERT.format(name=POTION_NAMES[kind], roman=ROMAN[tier]) if tier else AUTO_OFF_ALERT)
    text, markup = await render_kind(session, callback.from_user.id, kind)
    await safe_edit_text(callback.message, text, reply_markup=markup)


async def send_auto_pushes(bot: Bot, session: AsyncSession, results: list[tuple[int, str, int, str]]) -> None:
    """Пуш, если авто-зелье выключилось (не хватило NHCoin или гений медицины не активен)."""
    for user_id, kind, tier, outcome in results:
        if outcome == "ok":
            continue
        reason = AUTO_REASON_COINS if outcome == "coins" else AUTO_REASON_LOCKED
        await notify_player(
            bot, session, user_id, NOTIFY_POTION,
            PUSH_AUTO_STOPPED.format(name=POTION_NAMES[kind], roman=ROMAN[tier], reason=reason),
        )
