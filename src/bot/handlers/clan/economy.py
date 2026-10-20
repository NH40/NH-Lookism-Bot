"""Кланы — земли и здания, казна, магазин клана, журнал, уровни, обменник (хендлеры)."""
from __future__ import annotations

from bot.config.clan import clan_donate_price
from bot.constant.clan import CB_CLAN_LEVEL_BUY
from bot.keyboards.clan import levels_menu
from bot.texts.clan import LEVEL_BOUGHT_ALERT, LEVELS_NO_BUYERS

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.clan import (
    CLAN_SHOP_TICKET_PRICE_STEP,
    CLAN_SHOP_TICKETS_DAILY_LIMIT,
    CLAN_CONTRACT_HOURS,
    CLAN_BUILDINGS,
    CLAN_BUY_LANDS_MAX,
    CLAN_DEMOLISH_REFUND,
    CLAN_DONATE_LEVELS,
    CLAN_LANDS_PER_DONATE_LEVEL,
    CLAN_LOG_PAGE,
    building_price,
)
from bot.constant.clan import (
    BUILDINGS,
    CB_CLAN_BUILD_DOWN_PREFIX,
    CB_CLAN_BUILD_PREFIX,
    CB_CLAN_BUILD_UP_PREFIX,
    CB_CLAN_BUY_LAND,
    CB_CLAN_DONATE_COINS,
    CB_CLAN_EXCHANGE,
    CB_CLAN_EXCHANGE_MEMBER_PREFIX,
    CB_CLAN_EXCHANGE_RES_PREFIX,
    CB_CLAN_LANDS,
    CB_CLAN_LEVELS,
    CB_CLAN_LOG,
    CB_CLAN_SHOP,
    CB_CLAN_SHOP_MERCS,
    CB_CLAN_SHOP_MERCS_PREFIX,
    CB_CLAN_SHOP_POTION_PREFIX,
    CB_CLAN_SHOP_TICKETS,
    CB_CLAN_STATS_PREFIX,
    CB_CLAN_TREASURY,
    MANAGER_RANKS,
)
from bot.constant.resource import RES_COINS, RESOURCES
from bot.constant.settings import NOTIFY_CLAN
from bot.db.repositories import business as business_repo
from bot.db.repositories import clan as clan_repo
from bot.handlers.clan.clan import error_text, send_screen
from bot.keyboards.clan import (
    back_menu,
    building_menu,
    exchange_members_menu,
    exchange_res_menu,
    lands_menu,
    mercs_menu,
    shop_menu,
    treasury_menu,
)
from bot.services import clan as clan_service
from bot.services.contract import terms as contract_terms
from bot.services.resource import balance
from bot.services.settings import notify_player
from bot.states.clan import ClanStates
from bot.texts.clan import (
    AMOUNT_INVALID,
    BUILDING_ABOUT,
    BUILDING_FULL,
    BUILDING_NAMES,
    BUILDING_NEXT,
    BUILDING_SCREEN,
    DONATE_PROMPT,
    DONATED,
    DONE_ALERT,
    EXCHANGE_AMOUNT,
    EXCHANGE_NONE,
    EXCHANGE_PICK,
    EXCHANGE_RES,
    EXCHANGED,
    LANDS_BUILDING_LINE,
    LANDS_NO_BUILDINGS,
    LANDS_SCREEN,
    LEVEL_LINE,
    LEVELS_SCREEN,
    LOG_EMPTY,
    LOG_LINE,
    LOG_SCREEN,
    MERCS_PROMPT,
    MERCS_SCREEN,
    PUSH_EXCHANGE,
    SHOP_DONE,
    SHOP_TICKETS_PROMPT,
    SHOP_SCREEN,
    TREASURY_SCREEN,
)
from bot.texts.development import describe_level
from bot.texts.resource import amount_label, resource_label
from bot.utils.formatting import esc, format_number

router = Router(name="clan_economy")


async def _member(callback: CallbackQuery, session: AsyncSession, ranks=None):
    try:
        if ranks:
            return await clan_service.require_member(session, callback.from_user.id, ranks)
        return await clan_service.require_member(session, callback.from_user.id)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return None


def _number(text: str | None) -> int | None:
    raw = (text or "").replace(" ", "").replace("_", "")
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


# --- земли и здания ---

async def render_lands(session: AsyncSession, user_id: int):
    lv = await clan_service.lands_view(session, user_id)
    member = await clan_service.member_of(session, user_id)
    lines = "".join(
        LANDS_BUILDING_LINE.format(name=BUILDING_NAMES[k], count=lv.buildings[k], max=CLAN_BUILDINGS[k][0]) for k in BUILDINGS if lv.buildings.get(k)
    ) or LANDS_NO_BUILDINGS
    text = LANDS_SCREEN.format(
        lands=lv.clan.lands, max_lands=lv.max_lands, used=lv.used, free=max(0, lv.clan.lands - lv.used),
        treasury=format_number(lv.clan.treasury), buy_max=CLAN_BUY_LANDS_MAX, per_level=CLAN_LANDS_PER_DONATE_LEVEL, buildings=lines,
    )
    return text, lands_menu(lv.buildings, lv.next_land_price, member.rank in MANAGER_RANKS)


@router.callback_query(F.data == CB_CLAN_LANDS)
async def cb_lands(callback: CallbackQuery, session: AsyncSession) -> None:
    if await _member(callback, session) is None:
        return
    await callback.answer()
    text, markup = await render_lands(session, callback.from_user.id)
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, markup)


@router.callback_query(F.data == CB_CLAN_BUY_LAND)
async def cb_buy_land(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        await clan_service.buy_land(session, redis, callback.from_user.id)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(DONE_ALERT)
    text, markup = await render_lands(session, callback.from_user.id)
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, markup)


async def render_building(session: AsyncSession, user_id: int, kind: str):
    lv = await clan_service.lands_view(session, user_id)
    member = await clan_service.member_of(session, user_id)
    count, cap = lv.buildings.get(kind, 0), CLAN_BUILDINGS[kind][0]
    price = building_price(kind, count) if count < cap else None
    refund = int(building_price(kind, count - 1) * CLAN_DEMOLISH_REFUND) if count else None
    text = BUILDING_SCREEN.format(
        name=f"<b>{BUILDING_NAMES[kind]}</b>", about=BUILDING_ABOUT[kind], count=count, max=cap,
        next=BUILDING_NEXT.format(price=format_number(price)) if price else BUILDING_FULL,
    )
    return text, building_menu(kind, price, refund, member.rank in MANAGER_RANKS)


@router.callback_query(F.data.startswith(CB_CLAN_BUILD_PREFIX))
async def cb_building(callback: CallbackQuery, session: AsyncSession) -> None:
    kind = callback.data.removeprefix(CB_CLAN_BUILD_PREFIX)
    if kind not in BUILDINGS or await _member(callback, session) is None:
        return
    await callback.answer()
    text, markup = await render_building(session, callback.from_user.id, kind)
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, markup)


async def _building_action(callback: CallbackQuery, session: AsyncSession, redis: Redis, kind: str, action) -> None:
    if kind not in BUILDINGS:
        await callback.answer()
        return
    try:
        await action(session, redis, callback.from_user.id, kind)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(DONE_ALERT)
    text, markup = await render_building(session, callback.from_user.id, kind)
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, markup)


@router.callback_query(F.data.startswith(CB_CLAN_BUILD_UP_PREFIX))
async def cb_build_up(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    await _building_action(callback, session, redis, callback.data.removeprefix(CB_CLAN_BUILD_UP_PREFIX), clan_service.build)


@router.callback_query(F.data.startswith(CB_CLAN_BUILD_DOWN_PREFIX))
async def cb_build_down(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    await _building_action(callback, session, redis, callback.data.removeprefix(CB_CLAN_BUILD_DOWN_PREFIX), clan_service.demolish)


# --- казна ---

async def _coins(session: AsyncSession, user_id: int) -> int:
    wallet = await business_repo.get_wallet(session, user_id)
    return wallet.nh_coins if wallet else 0


@router.callback_query(F.data == CB_CLAN_TREASURY)
async def cb_treasury(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    member = await _member(callback, session)
    if member is None:
        return
    clan = await clan_repo.get(session, member.clan_id)
    await callback.answer()
    text = TREASURY_SCREEN.format(treasury=format_number(clan.treasury), coins=format_number(await _coins(session, callback.from_user.id)))
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, treasury_menu())


@router.callback_query(F.data == CB_CLAN_DONATE_COINS)
async def cb_donate(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if await _member(callback, session) is None:
        return
    await state.set_state(ClanStates.waiting_donate)
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message,
                      DONATE_PROMPT.format(coins=format_number(await _coins(session, callback.from_user.id))), back_menu(CB_CLAN_TREASURY))


@router.message(ClanStates.waiting_donate)
async def on_donate(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    amount = _number(message.text)
    if amount is None:
        await message.answer(AMOUNT_INVALID, reply_markup=back_menu(CB_CLAN_TREASURY))
        return
    try:
        treasury = await clan_service.donate(session, redis, message.from_user.id, amount)
    except clan_service.ClanError as exc:
        await message.answer(error_text(exc), reply_markup=back_menu(CB_CLAN_TREASURY))
        return
    await state.clear()
    await message.answer(DONATED.format(treasury=format_number(treasury)), reply_markup=back_menu())


# --- магазин клана ---

async def render_shop(session: AsyncSession, user_id: int):
    member = await clan_service.member_of(session, user_id)
    clan = await clan_repo.get(session, member.clan_id)
    members = await clan_repo.count_members(session, clan.id)
    text = SHOP_SCREEN.format(treasury=format_number(clan.treasury), members=members)
    return text, shop_menu(members, clan_service.tickets_price, clan_service.potion_price, clan_service.tickets_bought_today(clan))


@router.callback_query(F.data == CB_CLAN_SHOP)
async def cb_shop(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    if await _member(callback, session) is None:
        return
    await callback.answer()
    text, markup = await render_shop(session, callback.from_user.id)
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, markup)


async def _shop_done(callback: CallbackQuery, session: AsyncSession, price: int) -> None:
    await callback.answer(SHOP_DONE.format(price=format_number(price)).replace("<b>", "").replace("</b>", ""), show_alert=True)
    text, markup = await render_shop(session, callback.from_user.id)
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, markup)


@router.callback_query(F.data == CB_CLAN_SHOP_TICKETS)
async def cb_shop_tickets(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    member = await _member(callback, session, MANAGER_RANKS)
    if member is None:
        return
    clan = await clan_repo.get(session, member.clan_id)
    members = await clan_repo.count_members(session, clan.id)
    bought = clan_service.tickets_bought_today(clan)
    await state.set_state(ClanStates.waiting_shop_tickets)
    await callback.answer()
    text = SHOP_TICKETS_PROMPT.format(
        members=members, price=format_number(clan_service.tickets_price(1, members, bought)),
        step=format_number(CLAN_SHOP_TICKET_PRICE_STEP), bought=format_number(bought),
        limit=format_number(CLAN_SHOP_TICKETS_DAILY_LIMIT), treasury=format_number(clan.treasury),
    )
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, back_menu(CB_CLAN_SHOP))


@router.message(ClanStates.waiting_shop_tickets)
async def on_shop_tickets(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    tickets = _number(message.text)
    if tickets is None:
        await message.answer(AMOUNT_INVALID, reply_markup=back_menu(CB_CLAN_SHOP))
        return
    try:
        price, _ = await clan_service.shop_tickets(session, redis, message.from_user.id, tickets)
    except clan_service.ClanError as exc:
        await message.answer(error_text(exc), reply_markup=back_menu(CB_CLAN_SHOP))
        return
    await state.clear()
    await message.answer(SHOP_DONE.format(price=format_number(price)), reply_markup=back_menu(CB_CLAN_SHOP))


@router.callback_query(F.data.startswith(CB_CLAN_SHOP_POTION_PREFIX))
async def cb_shop_potion(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    kind, _, tier = callback.data.removeprefix(CB_CLAN_SHOP_POTION_PREFIX).partition(":")
    if not tier.isdigit():
        await callback.answer()
        return
    try:
        price, _ = await clan_service.shop_potion(session, redis, callback.from_user.id, kind, int(tier))
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await _shop_done(callback, session, price)


@router.callback_query(F.data == CB_CLAN_SHOP_MERCS)
async def cb_shop_mercs(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    if await _member(callback, session, MANAGER_RANKS) is None:
        return
    t = await contract_terms(session, callback.from_user.id)
    ranks = [(r, clan_service.contract_unit_price(r)) for r in t.ranks[:12]]
    await callback.answer()
    text = MERCS_SCREEN.format(ceiling=t.ceiling, hours=CLAN_CONTRACT_HOURS)
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, mercs_menu(ranks))


@router.callback_query(F.data.startswith(CB_CLAN_SHOP_MERCS_PREFIX))
async def cb_shop_mercs_rank(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    rank = callback.data.removeprefix(CB_CLAN_SHOP_MERCS_PREFIX)
    member = await _member(callback, session, MANAGER_RANKS)
    if member is None:
        return
    clan = await clan_repo.get(session, member.clan_id)
    await state.set_state(ClanStates.waiting_mercs)
    await state.update_data(rank=rank)
    await callback.answer()
    text = MERCS_PROMPT.format(
        rank=rank, hours=CLAN_CONTRACT_HOURS, price=format_number(clan_service.contract_unit_price(rank)), treasury=format_number(clan.treasury)
    )
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, back_menu(CB_CLAN_SHOP_MERCS))


@router.message(ClanStates.waiting_mercs)
async def on_mercs(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    quantity = _number(message.text)
    rank = (await state.get_data()).get("rank", "")
    if quantity is None:
        await message.answer(AMOUNT_INVALID, reply_markup=back_menu(CB_CLAN_SHOP_MERCS))
        return
    t = await contract_terms(session, message.from_user.id)
    try:
        price = await clan_service.shop_contracts(session, redis, message.from_user.id, rank, quantity, t.ceiling)
    except clan_service.ClanError as exc:
        await message.answer(error_text(exc), reply_markup=back_menu(CB_CLAN_SHOP_MERCS))
        return
    await state.clear()
    await message.answer(SHOP_DONE.format(price=format_number(price)), reply_markup=back_menu(CB_CLAN_SHOP))


# --- журнал и уровни ---

@router.callback_query(F.data == CB_CLAN_LOG)
async def cb_log(callback: CallbackQuery, session: AsyncSession) -> None:
    member = await _member(callback, session)
    if member is None:
        return
    rows = await clan_repo.recent_log(session, member.clan_id, CLAN_LOG_PAGE)
    lines = "".join(LOG_LINE.format(time=r.created_at.strftime("%d.%m %H:%M"), text=esc(r.text)) for r in rows) or LOG_EMPTY
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, LOG_SCREEN.format(rows=lines), back_menu())


@router.callback_query(F.data == CB_CLAN_LEVELS)
async def cb_levels(callback: CallbackQuery, session: AsyncSession) -> None:
    member = await _member(callback, session)
    if member is None:
        return
    clan = await clan_repo.get(session, member.clan_id)
    lines = "".join(
        LEVEL_LINE.format(
            mark="✅" if n <= clan.donate_level else "🔒", n=n,
            effect=describe_level({"eco": spec.get("eco", {})}) + f"; рота в войне: +{round(spec.get('combat', {}).get('attack', 0) * 100)}% атаки; земли +{CLAN_LANDS_PER_DONATE_LEVEL}",
        )
        for n, spec in enumerate(CLAN_DONATE_LEVELS, 1)
    )
    buyers = await clan_repo.donate_buyers(session, clan.id)
    names = await clan_repo.member_labels(session, [u for u, _ in buyers]) if buyers else {}
    buyers_text = ", ".join(f"{names.get(u, (str(u),))[0]} ({format_number(p)} 💎)" for u, p in buyers) or LEVELS_NO_BUYERS
    next_level = clan.donate_level + 1 if clan.donate_level < len(CLAN_DONATE_LEVELS) else None
    price = format_number(clan_donate_price(next_level)) if next_level else None
    await callback.answer()
    await send_screen(
        callback.bot, callback.message.chat.id, callback.message,
        LEVELS_SCREEN.format(level=clan.donate_level, levels=lines, buyers=buyers_text), levels_menu(next_level, price),
    )


@router.callback_query(F.data == CB_CLAN_LEVEL_BUY)
async def cb_level_buy(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    member = await _member(callback, session)
    if member is None:
        return
    try:
        level = await clan_service.buy_donate_level(session, redis, callback.from_user.id)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(LEVEL_BOUGHT_ALERT.format(level=level), show_alert=True)
    await cb_levels(callback, session)


# --- обменник ---

@router.callback_query(F.data == CB_CLAN_EXCHANGE)
async def cb_exchange(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    member = await _member(callback, session)
    if member is None:
        return
    ids = [uid for uid in await clan_repo.member_ids(session, member.clan_id) if uid != callback.from_user.id]
    if not ids:
        await callback.answer(EXCHANGE_NONE, show_alert=True)
        return
    labels = await clan_repo.member_labels(session, ids)
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, EXCHANGE_PICK, exchange_members_menu([(u, labels[u][0]) for u in ids]))


@router.callback_query(F.data.startswith(CB_CLAN_EXCHANGE_MEMBER_PREFIX))
async def cb_exchange_member(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    raw = callback.data.removeprefix(CB_CLAN_EXCHANGE_MEMBER_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    name = (await clan_repo.member_labels(session, [int(raw)])).get(int(raw), ("—", None))[0]
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, EXCHANGE_RES.format(name=esc(name)), exchange_res_menu(int(raw)))


@router.callback_query(F.data.startswith(CB_CLAN_EXCHANGE_RES_PREFIX))
async def cb_exchange_res(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    uid_raw, _, res = callback.data.removeprefix(CB_CLAN_EXCHANGE_RES_PREFIX).partition(":")
    if not uid_raw.isdigit() or res not in RESOURCES:
        await callback.answer()
        return
    name = (await clan_repo.member_labels(session, [int(uid_raw)])).get(int(uid_raw), ("—", None))[0]
    await state.set_state(ClanStates.waiting_exchange)
    await state.update_data(target=int(uid_raw), res=res)
    await callback.answer()
    text = EXCHANGE_AMOUNT.format(res=resource_label(res), name=esc(name), have=amount_label(res, await balance(session, callback.from_user.id, res)))
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, back_menu(f"{CB_CLAN_EXCHANGE_MEMBER_PREFIX}{uid_raw}"))


@router.message(ClanStates.waiting_exchange)
async def on_exchange(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    amount = _number(message.text)
    data = await state.get_data()
    target, res = data.get("target"), data.get("res", RES_COINS)
    if amount is None:
        await message.answer(AMOUNT_INVALID, reply_markup=back_menu(CB_CLAN_EXCHANGE))
        return
    try:
        await clan_service.exchange(session, redis, message.from_user.id, target, res, amount)
    except clan_service.ClanError as exc:
        await message.answer(error_text(exc), reply_markup=back_menu(CB_CLAN_EXCHANGE))
        return
    await state.clear()
    labels = await clan_repo.member_labels(session, [message.from_user.id, target])
    await message.answer(EXCHANGED.format(amount=amount_label(res, amount), name=esc(labels[target][0])), reply_markup=back_menu())
    await notify_player(message.bot, session, target, NOTIFY_CLAN, PUSH_EXCHANGE.format(name=esc(labels[message.from_user.id][0]), amount=amount_label(res, amount)))




# --- статистика вклада участников (2026-10-21) ---

def _ago(dt) -> str:
    from datetime import datetime, timezone

    from bot.texts.clan import STATS_SEEN_AGO, STATS_SEEN_NOW

    if dt is None:
        return STATS_SEEN_AGO.format(ago="давно")
    minutes = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
    if minutes < 10:
        return STATS_SEEN_NOW
    if minutes < 60:
        return STATS_SEEN_AGO.format(ago=f"{minutes} мин")
    if minutes < 48 * 60:
        return STATS_SEEN_AGO.format(ago=f"{minutes // 60} ч")
    return STATS_SEEN_AGO.format(ago=f"{minutes // 1440} дн")


@router.callback_query(F.data.startswith(CB_CLAN_STATS_PREFIX))
async def cb_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    from bot.constant.clan import STATS_SORT_TREASURY, STATS_SORTS
    from bot.keyboards.clan import stats_menu
    from bot.texts.clan import RANK_EMOJI, STATS_HINT, STATS_ROW, STATS_SCREEN, STATS_SORT_LABELS, STATS_TAKEN

    sort = callback.data.removeprefix(CB_CLAN_STATS_PREFIX)
    if sort not in STATS_SORTS:
        sort = STATS_SORT_TREASURY
    if await _member(callback, session) is None:
        return
    rows = await clan_service.member_stats(session, callback.from_user.id, sort)
    n = format_number
    lines = "".join(
        STATS_ROW.format(
            place=i + 1, emoji=RANK_EMOJI.get(r["rank"], "👤"), name=esc(r["name"]), seen=_ago(r["last_active_at"]),
            treasury=n(r["treasury"]), units=n(r["garrison_units"]), power=n(r["garrison_power"]),
            taken=STATS_TAKEN.format(taken=n(r["garrison_taken"])) if r["garrison_taken"] else "",
            shop=n(r["shop_spent"]), build=n(r["build_spent"]), wars=r["wars"], wars_won=r["wars_won"],
            lands=r["lands_won"], exchanges=r["exchanges"],
        )
        for i, r in enumerate(rows)
    )
    text = STATS_SCREEN.format(sort=STATS_SORT_LABELS[sort], rows=lines)
    if len(text) + len(STATS_HINT) < 4000:
        text += STATS_HINT
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text[:4090], stats_menu(sort))
