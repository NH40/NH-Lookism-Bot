"""Кланы — клановая рота и война за земли (хендлеры)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.card import CARD_BY_CODE
from bot.config.clan import CLAN_WAR_SHIELD_HOURS, CLAN_WAR_TREASURY_PERCENT
from bot.constant.clan import (
    CB_CLAN_GAR_REVOKE_PREFIX,
    GARRISON_FREE_RANKS,
    CB_CLAN_GAR_ACCESS,
    CB_CLAN_GAR_APPROVE_PREFIX,
    CB_CLAN_GAR_DENY_PREFIX,
    CB_CLAN_GAR_PUT,
    CB_CLAN_GAR_PUT_CARD_PREFIX,
    CB_CLAN_GAR_PUT_CARDS,
    CB_CLAN_GAR_PUT_SQUAD_PREFIX,
    CB_CLAN_GAR_REQUEST,
    CB_CLAN_GAR_TAKE,
    CB_CLAN_GAR_TAKE_CARD_PREFIX,
    CB_CLAN_GAR_TAKE_SQUAD_PREFIX,
    CB_CLAN_GARRISON,
    CB_CLAN_WAR,
    CB_CLAN_WAR_ATTACK_PREFIX,
    CB_CLAN_WAR_TARGETS_PREFIX,
    GARRISON_CARD,
    GARRISON_STATIST,
    MANAGER_RANKS,
)
from bot.constant.settings import NOTIFY_CLAN, NOTIFY_CLAN_WAR
from bot.db.repositories import card as card_repo
from bot.db.repositories import clan as clan_repo
from bot.handlers.clan.clan import error_text, send_screen
from bot.keyboards.clan import (
    access_menu,
    back_menu,
    garrison_menu,
    garrison_put_menu,
    items_menu,
    take_menu,
    war_confirm_menu,
    war_menu,
    war_targets_menu,
)
from bot.services import clan as clan_service
from bot.services.extra import list_squads
from bot.services.resource import StatistKey
from bot.services.settings import notify_player
from bot.states.clan import ClanStates
from bot.texts.clan import (
    GARRISON_CONTRACTS,
    GARRISON_CONTRACT_ROW,
    PUSH_GAR_REVOKED,
    AMOUNT_INVALID,
    BUILDING_NAMES,
    ERRORS,
    GAR_ACCESS_EMPTY,
    GAR_ACCESS_HEADER,
    GAR_AMOUNT,
    GAR_DONE,
    GAR_NOTHING,
    GAR_PICK_CARD,
    GAR_PICK_SQUAD,
    GAR_PICK_TAKE,
    GAR_PUT_PICK,
    GAR_REQUESTED_ALERT,
    GARRISON_CARDS,
    GARRISON_EMPTY,
    GARRISON_NEEDS_APPROVAL,
    GARRISON_PENDING,
    GARRISON_ROW,
    GARRISON_SCREEN,
    GARRISON_STATISTS,
    GARRISON_TENURE,
    PUSH_GAR_APPROVED,
    PUSH_GAR_DENIED,
    PUSH_GAR_REQUEST,
    WAR_BUILDINGS_LOST,
    WAR_CONFIRM,
    WAR_COOLDOWN,
    WAR_HISTORY_EMPTY,
    WAR_HISTORY_HEAD,
    WAR_HISTORY_LINE,
    WAR_HISTORY_LOSS,
    WAR_HISTORY_WIN,
    WAR_READY,
    WAR_RESULT,
    WAR_SCREEN,
    WAR_SHIELD,
    WAR_TARGETS,
    WAR_VERDICT_LOSS,
    WAR_VERDICT_WIN,
)
from bot.texts.gang import squad_title
from bot.utils.formatting import esc, format_countdown, format_number

router = Router(name="clan_garrison")


def _title(key: StatistKey) -> str:
    return squad_title(key.rank, key.stars, key.training_level, key.school, key.school_level)


def _card_name(code: str) -> str:
    card = CARD_BY_CODE.get(code)
    return card.name if card else code


async def _member(callback: CallbackQuery, session: AsyncSession, ranks=None):
    try:
        if ranks:
            return await clan_service.require_member(session, callback.from_user.id, ranks)
        return await clan_service.require_member(session, callback.from_user.id)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return None


# --- рота ---

async def render_garrison(session: AsyncSession, user_id: int):
    gv = await clan_service.garrison_view(session, user_id)
    statists = GARRISON_STATISTS.format(rows="".join(
        GARRISON_ROW.format(name=esc(_title(k)), quantity=format_number(q), power=format_number(round(p))) for k, q, p in gv.statists
    )) if gv.statists else ""
    cards = GARRISON_CARDS.format(rows="".join(
        GARRISON_ROW.format(name=esc(_card_name(c)), quantity=format_number(q), power=format_number(p)) for c, q, p in gv.cards
    )) if gv.cards else ""
    contracts = GARRISON_CONTRACTS.format(rows="".join(
        GARRISON_CONTRACT_ROW.format(rank=r, quantity=format_number(q), power=format_number(round(p)), countdown=format_countdown(left))
        for r, q, p, left in gv.contracts
    )) if gv.contracts else ""
    status = GARRISON_TENURE.format(countdown=format_countdown(gv.take_in_seconds)) if not gv.can_take else ""
    if gv.needs_approval:
        status += GARRISON_PENDING if gv.pending else GARRISON_NEEDS_APPROVAL
    text = GARRISON_SCREEN.format(
        power=format_number(gv.power), statists=statists, cards=cards if (statists or cards or contracts) else GARRISON_EMPTY,
        contracts=contracts, tenure=status,
    )
    return text, garrison_menu(can_request=gv.needs_approval and not gv.pending)


@router.callback_query(F.data == CB_CLAN_GARRISON)
async def cb_garrison(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    if await _member(callback, session) is None:
        return
    await callback.answer()
    text, markup = await render_garrison(session, callback.from_user.id)
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, markup)


@router.callback_query(F.data == CB_CLAN_GAR_PUT)
async def cb_gar_put(callback: CallbackQuery, session: AsyncSession) -> None:
    if await _member(callback, session) is None:
        return
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, GAR_PUT_PICK, garrison_put_menu())


async def _ask(callback: CallbackQuery, state: FSMContext, mode: str, kind: str, code: str, label: str, have: int) -> None:
    await state.set_state(ClanStates.waiting_garrison)
    await state.update_data(mode=mode, kind=kind, code=code)
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message,
                      GAR_AMOUNT.format(item=esc(label), have=format_number(have)), back_menu(CB_CLAN_GARRISON))


@router.callback_query(F.data.startswith(CB_CLAN_GAR_PUT_SQUAD_PREFIX))
async def cb_gar_put_squad(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    code = callback.data.removeprefix(CB_CLAN_GAR_PUT_SQUAD_PREFIX)
    if await _member(callback, session) is None:
        return
    squads = [sq for sq in await list_squads(session, callback.from_user.id) if sq.attack + sq.defense > 0]
    if not code:
        items = [
            (StatistKey(sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level).encode(),
             squad_title(sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level), sq.attack + sq.defense)
            for sq in squads
        ]
        if not items:
            await callback.answer(GAR_NOTHING, show_alert=True)
            return
        await callback.answer()
        await send_screen(callback.bot, callback.message.chat.id, callback.message, GAR_PICK_SQUAD, items_menu(items, CB_CLAN_GAR_PUT_SQUAD_PREFIX, CB_CLAN_GAR_PUT))
        return
    try:
        key = StatistKey.decode(code)
    except ValueError:
        await callback.answer()
        return
    have = sum(sq.attack + sq.defense for sq in squads if StatistKey(sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level) == key)
    await _ask(callback, state, "put", GARRISON_STATIST, code, _title(key), have)


@router.callback_query(F.data == CB_CLAN_GAR_PUT_CARDS)
async def cb_gar_put_cards(callback: CallbackQuery, session: AsyncSession) -> None:
    if await _member(callback, session) is None:
        return
    totals: dict[str, int] = {}
    for s in await card_repo.list_stacks(session, callback.from_user.id):
        totals[s.card_code] = totals.get(s.card_code, 0) + s.quantity
    items = [(code, _card_name(code), q) for code, q in sorted(totals.items()) if q > 0]
    if not items:
        await callback.answer(GAR_NOTHING, show_alert=True)
        return
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, GAR_PICK_CARD, items_menu(items, CB_CLAN_GAR_PUT_CARD_PREFIX, CB_CLAN_GAR_PUT))


@router.callback_query(F.data.startswith(CB_CLAN_GAR_PUT_CARD_PREFIX))
async def cb_gar_put_card(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    code = callback.data.removeprefix(CB_CLAN_GAR_PUT_CARD_PREFIX)
    have = sum(s.quantity for s in await card_repo.list_stacks(session, callback.from_user.id) if s.card_code == code)
    await _ask(callback, state, "put", GARRISON_CARD, code, _card_name(code), have)


@router.callback_query(F.data == CB_CLAN_GAR_TAKE)
async def cb_gar_take(callback: CallbackQuery, session: AsyncSession) -> None:
    if await _member(callback, session) is None:
        return
    gv = await clan_service.garrison_view(session, callback.from_user.id)
    if not gv.can_take:
        await callback.answer(ERRORS["tenure"], show_alert=True)
        return
    if gv.needs_approval:
        await callback.answer(ERRORS["approval_pending" if gv.pending else "needs_approval"], show_alert=True)
        return
    statists = [(k.encode(), _title(k), q) for k, q, _ in gv.statists]
    cards = [(c, _card_name(c), q) for c, q, _ in gv.cards]
    if not statists and not cards:
        await callback.answer(GAR_NOTHING, show_alert=True)
        return
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, GAR_PICK_TAKE, take_menu(statists, cards))


@router.callback_query(F.data.startswith(CB_CLAN_GAR_TAKE_SQUAD_PREFIX))
async def cb_gar_take_squad(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    code = callback.data.removeprefix(CB_CLAN_GAR_TAKE_SQUAD_PREFIX)
    try:
        key = StatistKey.decode(code)
    except ValueError:
        await callback.answer()
        return
    gv = await clan_service.garrison_view(session, callback.from_user.id)
    have = next((q for k, q, _ in gv.statists if k == key), 0)
    await _ask(callback, state, "take", GARRISON_STATIST, code, _title(key), have)


@router.callback_query(F.data.startswith(CB_CLAN_GAR_TAKE_CARD_PREFIX))
async def cb_gar_take_card(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    code = callback.data.removeprefix(CB_CLAN_GAR_TAKE_CARD_PREFIX)
    gv = await clan_service.garrison_view(session, callback.from_user.id)
    have = next((q for c, q, _ in gv.cards if c == code), 0)
    await _ask(callback, state, "take", GARRISON_CARD, code, _card_name(code), have)


@router.message(ClanStates.waiting_garrison)
async def on_garrison_amount(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    raw = (message.text or "").replace(" ", "").replace("_", "")
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer(AMOUNT_INVALID, reply_markup=back_menu(CB_CLAN_GARRISON))
        return
    data = await state.get_data()
    mode, kind, code, amount, user_id = data.get("mode"), data.get("kind"), data.get("code", ""), int(raw), message.from_user.id
    try:
        if mode == "put" and kind == GARRISON_STATIST:
            await clan_service.put_statists(session, redis, user_id, StatistKey.decode(code), amount)
        elif mode == "put":
            await clan_service.put_cards(session, redis, user_id, code, amount)
        elif kind == GARRISON_STATIST:
            await clan_service.take_statists_from(session, redis, user_id, StatistKey.decode(code), amount)
        else:
            await clan_service.take_cards_from(session, redis, user_id, code, amount)
    except clan_service.ClanError as exc:
        await message.answer(error_text(exc), reply_markup=back_menu(CB_CLAN_GARRISON))
        return
    await state.clear()
    await message.answer(GAR_DONE)
    text, markup = await render_garrison(session, user_id)
    await message.answer(text, reply_markup=markup)


# --- доступ рядовых к роте (одобрение владельца или зама — один раз) ---

@router.callback_query(F.data == CB_CLAN_GAR_REQUEST)
async def cb_gar_request(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        clan_id = await clan_service.request_access(session, callback.from_user.id)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(GAR_REQUESTED_ALERT, show_alert=True)
    name = (await clan_repo.member_labels(session, [callback.from_user.id]))[callback.from_user.id][0]
    for officer in (await clan_repo.officers(session, clan_id)).values():
        await notify_player(callback.bot, session, officer, NOTIFY_CLAN, PUSH_GAR_REQUEST.format(name=esc(name)))
    text, markup = await render_garrison(session, callback.from_user.id)
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, markup)


async def _show_access(callback: CallbackQuery, session: AsyncSession) -> None:
    items = await clan_service.access_list(session, callback.from_user.id)
    await send_screen(callback.bot, callback.message.chat.id, callback.message,
                      GAR_ACCESS_HEADER + ("" if items else GAR_ACCESS_EMPTY), access_menu(items))


@router.callback_query(F.data == CB_CLAN_GAR_ACCESS)
async def cb_gar_access(callback: CallbackQuery, session: AsyncSession) -> None:
    if await _member(callback, session, GARRISON_FREE_RANKS) is None:
        return
    await callback.answer()
    await _show_access(callback, session)


async def _resolve(callback: CallbackQuery, session: AsyncSession, raw: str, approved: bool) -> None:
    if not raw.isdigit():
        await callback.answer()
        return
    try:
        if approved:
            await clan_service.set_access(session, callback.from_user.id, int(raw), True)
        else:
            await clan_service.resolve_access(session, callback.from_user.id, int(raw), False)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer()
    await notify_player(callback.bot, session, int(raw), NOTIFY_CLAN, PUSH_GAR_APPROVED if approved else PUSH_GAR_DENIED)
    await _show_access(callback, session)


@router.callback_query(F.data.startswith(CB_CLAN_GAR_APPROVE_PREFIX))
async def cb_gar_approve(callback: CallbackQuery, session: AsyncSession) -> None:
    await _resolve(callback, session, callback.data.removeprefix(CB_CLAN_GAR_APPROVE_PREFIX), True)


@router.callback_query(F.data.startswith(CB_CLAN_GAR_DENY_PREFIX))
async def cb_gar_deny(callback: CallbackQuery, session: AsyncSession) -> None:
    await _resolve(callback, session, callback.data.removeprefix(CB_CLAN_GAR_DENY_PREFIX), False)


# --- война ---

async def render_war(session: AsyncSession, user_id: int):
    member = await clan_service.member_of(session, user_id)
    clan = await clan_service.my_clan(session, user_id)
    cooldown, shield = clan_service.cooldown_left(clan), clan_service.shield_left(clan)
    status = WAR_COOLDOWN.format(countdown=format_countdown(cooldown)) if cooldown else WAR_READY
    if shield:
        status += WAR_SHIELD.format(countdown=format_countdown(shield))
    wars = await clan_service.history(session, clan.id)
    history = (WAR_HISTORY_HEAD + "".join(
        WAR_HISTORY_LINE.format(
            mark="🏆" if (w.attacker_id == clan.id) == w.attacker_won else "💀",
            attacker=esc(w.attacker_name), defender=esc(w.defender_name),
            result=WAR_HISTORY_WIN.format(lands=w.lands_taken) if w.attacker_won else WAR_HISTORY_LOSS,
        )
        for w in wars
    )) if wars else WAR_HISTORY_EMPTY
    text = WAR_SCREEN.format(
        treasury_pct=CLAN_WAR_TREASURY_PERCENT, shield=CLAN_WAR_SHIELD_HOURS,
        power=format_number(await clan_service.clan_power(session, clan.id)), status=status, history=history,
    )
    return text, war_menu(member.rank in MANAGER_RANKS and not cooldown)


@router.callback_query(F.data == CB_CLAN_WAR)
async def cb_war(callback: CallbackQuery, session: AsyncSession) -> None:
    if await _member(callback, session) is None:
        return
    await callback.answer()
    text, markup = await render_war(session, callback.from_user.id)
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, markup)


@router.callback_query(F.data.startswith(CB_CLAN_WAR_TARGETS_PREFIX))
async def cb_war_targets(callback: CallbackQuery, session: AsyncSession) -> None:
    if await _member(callback, session, MANAGER_RANKS) is None:
        return
    raw = callback.data.removeprefix(CB_CLAN_WAR_TARGETS_PREFIX)
    targets, page, pages = await clan_service.targets(session, callback.from_user.id, int(raw) if raw.isdigit() else 0)
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message,
                      WAR_TARGETS.format(page=page + 1, pages=pages), war_targets_menu(targets, page, pages))


@router.callback_query(F.data.startswith(CB_CLAN_WAR_ATTACK_PREFIX))
async def cb_war_attack(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    cid_raw, _, ok = callback.data.removeprefix(CB_CLAN_WAR_ATTACK_PREFIX).partition(":")
    if not cid_raw.isdigit() or await _member(callback, session, MANAGER_RANKS) is None:
        return
    target = await clan_repo.get(session, int(cid_raw))
    if target is None:
        await callback.answer(ERRORS["clan_gone"], show_alert=True)
        return
    if not ok:
        await callback.answer()
        await send_screen(callback.bot, callback.message.chat.id, callback.message,
                          WAR_CONFIRM.format(name=esc(target.name), lands=target.lands), war_confirm_menu(target.id))
        return
    try:
        out = await clan_service.attack(session, redis, callback.from_user.id, target.id)
    except clan_service.ClanError as exc:
        value = format_countdown(exc.value) if exc.code in ("war_cooldown", "shielded") else exc.value
        await callback.answer(ERRORS[exc.code].format(value=value), show_alert=True)
        return
    await callback.answer()
    text = war_result_text(out)
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, back_menu(CB_CLAN_WAR))
    for uid in {*out.attacker_members, *out.defender_members} - {callback.from_user.id}:
        await notify_player(callback.bot, session, uid, NOTIFY_CLAN_WAR, text)


def war_result_text(out) -> str:
    if out.attacker_won:
        lost = WAR_BUILDINGS_LOST.format(list=", ".join(f"{BUILDING_NAMES[k]} ×{n}" for k, n in out.buildings_lost.items())) if out.buildings_lost else ""
        verdict = WAR_VERDICT_WIN.format(taken=out.lands_taken, gained=out.lands_gained, treasury=format_number(out.treasury_taken), buildings=lost)
    else:
        verdict = WAR_VERDICT_LOSS
    return WAR_RESULT.format(
        attacker=esc(out.attacker_name), defender=esc(out.defender_name), a_power=format_number(out.attacker_power),
        d_power=format_number(out.defender_power), rounds=out.rounds, a_dead=format_number(out.attacker_dead),
        d_dead=format_number(out.defender_dead), verdict=verdict,
    )


@router.callback_query(F.data.startswith(CB_CLAN_GAR_REVOKE_PREFIX))
async def cb_gar_revoke(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_CLAN_GAR_REVOKE_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    try:
        await clan_service.set_access(session, callback.from_user.id, int(raw), False)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer()
    await notify_player(callback.bot, session, int(raw), NOTIFY_CLAN, PUSH_GAR_REVOKED)
    await _show_access(callback, session)
