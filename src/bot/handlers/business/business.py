"""Бизнесы на районе — кофе/зал/магазин/нелегальный рынок/парламент, прокачка уровень/вместимость (хендлеры).

raw-notes «Карта» → «Бизнес». Экран бизнеса (кошелёк, накоплено, здания, районы,
прокачка) → экран района (здания на нём, стройка). Вход — «💼 Бизнес» в меню профиля,
`/business` и «💼 Бизнесы района» в карточке своего района на карте.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import action_lock
from bot.config.game import ACTION_LOCK_MS, BUSINESS_LEVEL_INCOME_BONUS_PERCENT
from bot.constant.business import (
    BUSINESS_TYPES,
    CB_BUSINESS_BUILD_PREFIX,
    CB_BUSINESS_COLLECT,
    CB_BUSINESS_DEMOLISH_ALL_ASK_PREFIX,
    CB_BUSINESS_DEMOLISH_ALL_PREFIX,
    CB_BUSINESS_DEMOLISH_EVERY_ALL,
    CB_BUSINESS_DEMOLISH_EVERY_ALL_ASK,
    CB_BUSINESS_DEMOLISH_EVERY_MENU,
    CB_BUSINESS_DEMOLISH_EVERY_PREFIX,
    CB_BUSINESS_DEMOLISH_MENU_PREFIX,
    CB_BUSINESS_DEMOLISH_PREFIX,
    CB_BUSINESS_DISTRICT_PREFIX,
    CB_BUSINESS_FILL_MENU_PREFIX,
    CB_BUSINESS_FILL_PREFIX,
    CB_BUSINESS_OPEN,
    CB_BUSINESS_PAGE_PREFIX,
    CB_BUSINESS_UPGRADE_PREFIX,
    LOCK_ACTION_BUSINESS,
    UPGRADE_CAPACITY,
    UPGRADE_LEVEL,
)
from bot.keyboards.business import (
    demolish_confirm_menu,
    demolish_everywhere_confirm_menu,
    demolish_everywhere_menu,
    demolish_menu,
    district_menu,
    fill_menu,
    overview_menu,
)
from bot.services.business import (
    DistrictBusinesses,
    MaxUpgradeError,
    NoFreeSlotError,
    NotDistrictOwnerError,
    NotEnoughCoinsError,
    NothingToDemolishError,
    UnknownBusinessTypeError,
    build,
    build_all,
    collect,
    demolish,
    demolish_everywhere,
    get_districts_catalog,
    get_district_businesses,
    get_overview,
    upgrade,
)
from bot.services.gang import get_gang
from bot.texts.business import (
    BONUS_GYM,
    BONUS_LINE,
    BONUS_PARLIAMENT,
    BTN_DISTRICT,
    BTN_DISTRICT_IN_CITY,
    BUILD_HEADER,
    BUILD_LINE,
    BUILT,
    BUILT_ALL,
    DEMOLISH_ALL_CONFIRM,
    DEMOLISH_EVERY_ALL_CONFIRM,
    DEMOLISH_EVERY_SCREEN,
    DEMOLISHED_EVERYWHERE,
    DEMOLISH_SCREEN,
    DEMOLISHED,
    FILL_SCOPE_ALL,
    FILL_SCOPE_DISTRICT,
    FILL_SCREEN,
    NO_FREE_SLOTS_ANYWHERE,
    NOTHING_TO_DEMOLISH,
    BUSINESS_DESCRIPTIONS,
    BUSINESS_NAMES,
    BUSY,
    COLLECTED,
    DISTRICT_SCREEN,
    DISTRICTS_PICK,
    MAX_UPGRADE,
    NO_DISTRICTS,
    NO_FREE_SLOT,
    NO_FREE_SLOTS_BLOCK,
    NOT_DISTRICT_OWNER,
    NOT_ENOUGH_COINS,
    NOTHING_TO_COLLECT,
    OVERVIEW_HEADER,
    STORAGE_FILLS_IN,
    STORAGE_FULL,
    UPGRADE_COLLECTED,
    UPGRADED_CAPACITY,
    UPGRADED_LEVEL,
    buildings_summary,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.empire import TAX_LINE
from bot.utils.formatting import esc, format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="business")


async def _render_overview(session: AsyncSession, user_id: int, page: int):
    overview = await get_overview(session, user_id)
    wallet = overview.wallet
    bonuses = []
    if overview.gym_bonus_percent:
        bonuses.append(BONUS_GYM.format(value=overview.gym_bonus_percent))
    if overview.parliament_influence:
        bonuses.append(BONUS_PARLIAMENT.format(value=overview.parliament_influence))
    text = OVERVIEW_HEADER.format(
        coins=format_number(wallet.nh_coins),
        pending=format_number(wallet.pending),
        # Таймер хранилища имеет смысл, только когда есть что копить.
        storage_line=(
            ""
            if not wallet.counts
            else STORAGE_FILLS_IN.format(countdown=format_countdown(wallet.storage_full_in_seconds))
            if wallet.storage_full_in_seconds > 0
            else STORAGE_FULL
        ),
        per_minute=format_number(round(wallet.per_minute)),
        per_day=format_number(round(wallet.per_minute * 24 * 60)),
        tax_line=(
            TAX_LINE.format(
                emperor=f"@{esc(wallet.tax.emperor_username)}"
                if wallet.tax.emperor_username
                else esc(wallet.tax.emperor_name or "-"),
                percent=wallet.tax.percent,
            )
            if wallet.tax
            else ""
        ),
        buildings=buildings_summary(wallet.counts),
        bonus_line=BONUS_LINE.format(bonuses=" · ".join(bonuses)) if bonuses else "",
        level=wallet.level,
        level_bonus=wallet.level * BUSINESS_LEVEL_INCOME_BONUS_PERCENT,
        capacity=wallet.capacity,
        slots=overview.capacity_per_district,
        districts_line=DISTRICTS_PICK if overview.districts else NO_DISTRICTS,
    )
    # Город в подписи — только когда районы в нескольких городах (у круга), банде он лишний.
    multi_city = len({d.city_name for d in overview.districts}) > 1
    template = BTN_DISTRICT_IN_CITY if multi_city else BTN_DISTRICT
    markup = overview_menu(
        pending=wallet.pending,
        districts=[
            (
                d.district_id,
                template.format(
                    city=d.city_name, number=d.number, used=d.buildings, capacity=overview.capacity_per_district
                ),
            )
            for d in overview.districts
        ],
        page=page,
        level=wallet.level,
        level_cost=overview.level_cost,
        capacity=wallet.capacity,
        capacity_cost=overview.capacity_cost,
    )
    return text, markup


def _render_district(view: DistrictBusinesses):
    if view.free:
        lines = [
            BUILD_LINE.format(
                name=BUSINESS_NAMES[t], cost=format_number(view.build_costs[t]), description=BUSINESS_DESCRIPTIONS[t]
            )
            for t in BUSINESS_TYPES
        ]
        build_block = BUILD_HEADER + "\n".join(lines)
    else:
        build_block = NO_FREE_SLOTS_BLOCK
    text = DISTRICT_SCREEN.format(
        number=view.number,
        used=view.used,
        capacity=view.capacity,
        buildings=buildings_summary(view.counts),
        coins=format_number(view.nh_coins),
        build_block=build_block,
    )
    return text, district_menu(view.district_id, can_build=view.free > 0, costs=view.build_costs, has_buildings=view.used > 0)


async def _is_onboarded(session: AsyncSession, user_id: int) -> bool:
    # Банда — последний шаг онбординга: есть банда — есть город и районы могут быть.
    return await get_gang(session, user_id) is not None


@router.message(Command("business"))
async def cmd_business(message: Message, session: AsyncSession) -> None:
    if not await _is_onboarded(session, message.from_user.id):
        await message.answer(NOT_ONBOARDED)
        return
    text, markup = await _render_overview(session, message.from_user.id, 0)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == CB_BUSINESS_OPEN)
async def cb_business_open(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_onboarded(session, callback.from_user.id):
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    text, markup = await _render_overview(session, callback.from_user.id, 0)
    await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_BUSINESS_PAGE_PREFIX))
async def cb_business_page(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_onboarded(session, callback.from_user.id):
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        page = int(callback.data.removeprefix(CB_BUSINESS_PAGE_PREFIX))
    except ValueError:
        page = 0
    await callback.answer()
    text, markup = await _render_overview(session, callback.from_user.id, page)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_BUSINESS_COLLECT)
async def cb_business_collect(callback: CallbackQuery, session: AsyncSession) -> None:
    # Без Redis-лока: повторный клик ждёт FOR UPDATE первого и зачисляет ~0 (см. сервис).
    amount = await collect(session, callback.from_user.id)
    await callback.answer(COLLECTED.format(amount=format_number(amount)) if amount else NOTHING_TO_COLLECT)
    text, markup = await _render_overview(session, callback.from_user.id, 0)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_BUSINESS_DISTRICT_PREFIX))
async def cb_business_district(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        district_id = int(callback.data.removeprefix(CB_BUSINESS_DISTRICT_PREFIX))
        view = await get_district_businesses(session, callback.from_user.id, district_id)
    except ValueError:
        await callback.answer()
        return
    except NotDistrictOwnerError:
        await callback.answer(NOT_DISTRICT_OWNER, show_alert=True)
        return
    await callback.answer()
    text, markup = _render_district(view)
    await safe_edit_text(callback.message, text, reply_markup=markup)


async def _acquire(redis: Redis, user_id: int) -> str | None:
    key = action_lock(user_id, LOCK_ACTION_BUSINESS)
    return key if await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS) else None


@router.callback_query(F.data.startswith(CB_BUSINESS_BUILD_PREFIX))
async def cb_business_build(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user_id = callback.from_user.id
    try:
        district_raw, type_ = callback.data.removeprefix(CB_BUSINESS_BUILD_PREFIX).split(":")
        district_id = int(district_raw)
    except ValueError:
        await callback.answer()
        return

    lock = await _acquire(redis, user_id)
    if lock is None:
        await callback.answer(BUSY)
        return
    try:
        result = await build(session, user_id, district_id, type_)
    except UnknownBusinessTypeError:
        await callback.answer()
        return
    except NotDistrictOwnerError:
        await callback.answer(NOT_DISTRICT_OWNER, show_alert=True)
        return
    except NoFreeSlotError:
        await callback.answer(NO_FREE_SLOT, show_alert=True)
        return
    except NotEnoughCoinsError as exc:
        await callback.answer(
            NOT_ENOUGH_COINS.format(cost=format_number(exc.cost), balance=format_number(exc.balance)), show_alert=True
        )
        return
    finally:
        await redis.delete(lock)

    await callback.answer(
        BUILT.format(name=BUSINESS_NAMES[result.type], number=result.district_number, cost=format_number(result.cost))
    )
    text, markup = _render_district(await get_district_businesses(session, user_id, district_id))
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_BUSINESS_UPGRADE_PREFIX))
async def cb_business_upgrade(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user_id = callback.from_user.id
    kind = callback.data.removeprefix(CB_BUSINESS_UPGRADE_PREFIX)
    if kind not in (UPGRADE_LEVEL, UPGRADE_CAPACITY):
        await callback.answer()
        return

    lock = await _acquire(redis, user_id)
    if lock is None:
        await callback.answer(BUSY)
        return
    try:
        result = await upgrade(session, user_id, kind)
    except MaxUpgradeError:
        await callback.answer(MAX_UPGRADE, show_alert=True)
        return
    except NotEnoughCoinsError as exc:
        await callback.answer(
            NOT_ENOUGH_COINS.format(cost=format_number(exc.cost), balance=format_number(exc.balance)), show_alert=True
        )
        return
    finally:
        await redis.delete(lock)

    template = UPGRADED_LEVEL if kind == UPGRADE_LEVEL else UPGRADED_CAPACITY
    await callback.answer(template.format(level=result.new_level, cost=format_number(result.cost))
        + (UPGRADE_COLLECTED.format(amount=format_number(result.collected)) if result.collected else ""))
    text, markup = await _render_overview(session, user_id, 0)
    await safe_edit_text(callback.message, text, reply_markup=markup)


# --- застроить всё / снос ---


def _ids(raw: str) -> tuple[int, str | None]:
    """"12:cafe" -> (12, "cafe"); "12" -> (12, None). ValueError — мусор в callback."""
    district_raw, _, type_ = raw.partition(":")
    return int(district_raw), (type_ or None)


async def _fill_screen(session: AsyncSession, user_id: int, district_id: int):
    if district_id:
        view = await get_district_businesses(session, user_id, district_id)
        scope, free, coins, costs = FILL_SCOPE_DISTRICT.format(number=view.number), view.free, view.nh_coins, view.build_costs
    else:
        overview = await get_overview(session, user_id)
        costs = (await get_districts_catalog(session, user_id)).build_costs
        cap = overview.capacity_per_district
        scope, coins = FILL_SCOPE_ALL, overview.wallet.nh_coins
        free = sum(max(0, cap - d.buildings) for d in overview.districts)
    text = FILL_SCREEN.format(scope=scope, free=free, coins=format_number(coins))
    return text, fill_menu(district_id, costs)


@router.callback_query(F.data.startswith(CB_BUSINESS_FILL_MENU_PREFIX))
async def cb_business_fill_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        district_id, _ = _ids(callback.data.removeprefix(CB_BUSINESS_FILL_MENU_PREFIX))
        text, markup = await _fill_screen(session, callback.from_user.id, district_id)
    except ValueError:
        await callback.answer()
        return
    except NotDistrictOwnerError:
        await callback.answer(NOT_DISTRICT_OWNER, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_BUSINESS_FILL_PREFIX))
async def cb_business_fill(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user_id = callback.from_user.id
    try:
        district_id, type_ = _ids(callback.data.removeprefix(CB_BUSINESS_FILL_PREFIX))
    except ValueError:
        await callback.answer()
        return
    lock = await _acquire(redis, user_id)
    if lock is None:
        await callback.answer(BUSY)
        return
    try:
        result = await build_all(session, user_id, type_ or "", district_id or None)
    except UnknownBusinessTypeError:
        await callback.answer()
        return
    except NotDistrictOwnerError:
        await callback.answer(NOT_DISTRICT_OWNER, show_alert=True)
        return
    except NoFreeSlotError:
        await callback.answer(NO_FREE_SLOTS_ANYWHERE, show_alert=True)
        return
    except NotEnoughCoinsError as exc:
        await callback.answer(
            NOT_ENOUGH_COINS.format(cost=format_number(exc.cost), balance=format_number(exc.balance)), show_alert=True
        )
        return
    finally:
        await redis.delete(lock)
    await callback.answer(
        BUILT_ALL.format(
            name=BUSINESS_NAMES[result.type], count=result.built, districts=result.districts, cost=format_number(result.cost)
        ),
        show_alert=True,
    )
    if district_id:
        text, markup = _render_district(await get_district_businesses(session, user_id, district_id))
    else:
        text, markup = await _render_overview(session, user_id, 0)
    await safe_edit_text(callback.message, text, reply_markup=markup)


async def _demolish_screen(session: AsyncSession, user_id: int, district_id: int):
    view = await get_district_businesses(session, user_id, district_id)
    if not view.used:
        return _render_district(view)
    text = DEMOLISH_SCREEN.format(number=view.number, buildings=buildings_summary(view.counts))
    return text, demolish_menu(district_id, view.counts)


@router.callback_query(F.data.startswith(CB_BUSINESS_DEMOLISH_MENU_PREFIX))
async def cb_business_demolish_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        district_id, _ = _ids(callback.data.removeprefix(CB_BUSINESS_DEMOLISH_MENU_PREFIX))
        text, markup = await _demolish_screen(session, callback.from_user.id, district_id)
    except ValueError:
        await callback.answer()
        return
    except NotDistrictOwnerError:
        await callback.answer(NOT_DISTRICT_OWNER, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_BUSINESS_DEMOLISH_ALL_ASK_PREFIX))
async def cb_business_demolish_all_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        district_id, _ = _ids(callback.data.removeprefix(CB_BUSINESS_DEMOLISH_ALL_ASK_PREFIX))
        view = await get_district_businesses(session, callback.from_user.id, district_id)
    except ValueError:
        await callback.answer()
        return
    except NotDistrictOwnerError:
        await callback.answer(NOT_DISTRICT_OWNER, show_alert=True)
        return
    await callback.answer()
    text = DEMOLISH_ALL_CONFIRM.format(number=view.number, buildings=buildings_summary(view.counts))
    await safe_edit_text(callback.message, text, reply_markup=demolish_confirm_menu(district_id))


async def _do_demolish(callback: CallbackQuery, session: AsyncSession, redis: Redis, district_id: int, type_: str | None) -> None:
    user_id = callback.from_user.id
    lock = await _acquire(redis, user_id)
    if lock is None:
        await callback.answer(BUSY)
        return
    try:
        result = await demolish(session, user_id, district_id, type_)
    except UnknownBusinessTypeError:
        await callback.answer()
        return
    except NotDistrictOwnerError:
        await callback.answer(NOT_DISTRICT_OWNER, show_alert=True)
        return
    except NothingToDemolishError:
        await callback.answer(NOTHING_TO_DEMOLISH, show_alert=True)
        return
    finally:
        await redis.delete(lock)
    await callback.answer(DEMOLISHED.format(count=result.removed, number=result.district_number))
    text, markup = await _demolish_screen(session, user_id, district_id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_BUSINESS_DEMOLISH_ALL_PREFIX))
async def cb_business_demolish_all(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        district_id, _ = _ids(callback.data.removeprefix(CB_BUSINESS_DEMOLISH_ALL_PREFIX))
    except ValueError:
        await callback.answer()
        return
    await _do_demolish(callback, session, redis, district_id, None)


@router.callback_query(F.data.startswith(CB_BUSINESS_DEMOLISH_PREFIX))
async def cb_business_demolish(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        district_id, type_ = _ids(callback.data.removeprefix(CB_BUSINESS_DEMOLISH_PREFIX))
    except ValueError:
        await callback.answer()
        return
    if type_ is None:
        await callback.answer()
        return
    await _do_demolish(callback, session, redis, district_id, type_)


# --- снос во всех районах (пользователи 2026-10-20) ---

async def _everywhere_screen(session: AsyncSession, user_id: int):
    from bot.services.business import owned_counts

    counts = await owned_counts(session, user_id)
    text = DEMOLISH_EVERY_SCREEN.format(buildings=buildings_summary(counts))
    return text, demolish_everywhere_menu(counts), counts


@router.callback_query(F.data == CB_BUSINESS_DEMOLISH_EVERY_MENU)
async def cb_demolish_everywhere_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    text, markup, _ = await _everywhere_screen(session, callback.from_user.id)
    await callback.answer()
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_BUSINESS_DEMOLISH_EVERY_ALL_ASK)
async def cb_demolish_everywhere_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, counts = await _everywhere_screen(session, callback.from_user.id)
    if not counts:
        await callback.answer(NOTHING_TO_DEMOLISH, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message, DEMOLISH_EVERY_ALL_CONFIRM.format(count=format_number(sum(counts.values()))),
        reply_markup=demolish_everywhere_confirm_menu(),
    )


async def _do_demolish_everywhere(callback: CallbackQuery, session: AsyncSession, redis: Redis, type_: str | None) -> None:
    user_id = callback.from_user.id
    lock = await _acquire(redis, user_id)
    if lock is None:
        await callback.answer(BUSY)
        return
    try:
        removed = await demolish_everywhere(session, user_id, type_)
    except UnknownBusinessTypeError:
        await callback.answer()
        return
    except NothingToDemolishError:
        await callback.answer(NOTHING_TO_DEMOLISH, show_alert=True)
        return
    finally:
        await redis.delete(lock)
    await callback.answer(DEMOLISHED_EVERYWHERE.format(count=format_number(removed)), show_alert=True)
    text, markup, _ = await _everywhere_screen(session, user_id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_BUSINESS_DEMOLISH_EVERY_ALL)
async def cb_demolish_everywhere_all(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    await _do_demolish_everywhere(callback, session, redis, None)


@router.callback_query(F.data.startswith(CB_BUSINESS_DEMOLISH_EVERY_PREFIX))
async def cb_demolish_everywhere_type(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    await _do_demolish_everywhere(callback, session, redis, callback.data.removeprefix(CB_BUSINESS_DEMOLISH_EVERY_PREFIX))
