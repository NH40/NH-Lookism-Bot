"""Админка — Выдать/забрать что угодно (из карточки игрока): ресурсы, статисты, уник-карты,
свитки пропуска, опыт Battle Pass. Отрицательное число — забрать (ниже нуля не уйдёт)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.card import CARD_BY_CODE
from bot.constant.admin import CB_ADMIN_PLAYER_GIVE_PREFIX, SECTION_GIVE
from bot.constant.admin.players_admin import (
    AUDIT_GIVE_BP_XP,
    AUDIT_GIVE_CARD,
    AUDIT_GIVE_RESOURCE,
    AUDIT_GIVE_SCROLLS,
    AUDIT_GIVE_STATIST,
    CB_GIVE_CARD,
    CB_GIVE_MENU,
    CB_GIVE_RES_LIST,
    CB_GIVE_RES_PICK,
    CB_GIVE_SCROLLS,
    CB_GIVE_STATIST,
    CB_GIVE_XP,
    GIVE_KIND_CARD,
    GIVE_KIND_RESOURCE,
    GIVE_KIND_SCROLLS,
    GIVE_KIND_STATIST,
    GIVE_KIND_XP,
)
from bot.constant.characteristic import RANK_LADDER
from bot.constant.resource import RESOURCES
from bot.handlers.admin.common import guard, parse_id
from bot.handlers.admin.player_target import (
    edit_screen,
    load_target,
    name_of,
    parse_int,
    reply_card,
    sign,
)
from bot.keyboards.admin.players_admin import cancel_to, give_menu, give_resources
from bot.services import resource
from bot.services.admin import audit, players_admin, roles
from bot.services.resource.statists import StatistKey
from bot.states.admin_players import AdminGiveStates
from bot.texts.admin import players_admin as t
from bot.texts.resource import amount_label, resource_label
from bot.utils.formatting import esc, format_number

router = Router(name="admin_give")

_RANKS_HINT = ", ".join(RANK_LADDER[:12]) + "…"
_HINT_LIMIT = 8


@router.callback_query(F.data.startswith((CB_ADMIN_PLAYER_GIVE_PREFIX, CB_GIVE_MENU)))
async def cb_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_GIVE):
        return
    prefix = CB_GIVE_MENU if callback.data.startswith(CB_GIVE_MENU) else CB_ADMIN_PLAYER_GIVE_PREFIX
    user = await load_target(callback, session, parse_id(callback.data, prefix))
    if user is None:
        return
    await state.clear()
    await edit_screen(callback, t.GIVE_MENU.format(name=name_of(user)), give_menu(user.id))


@router.callback_query(F.data.startswith(CB_GIVE_RES_LIST))
async def cb_resources(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_GIVE):
        return
    user = await load_target(callback, session, parse_id(callback.data, CB_GIVE_RES_LIST))
    if user is None:
        return
    await state.clear()
    balances = await resource.balances(session, user.id)
    lines = "\n".join(f"{resource_label(c)}: <b>{amount_label(c, v)}</b>" for c, v in balances.items())
    await edit_screen(callback, t.GIVE_RES_LIST.format(name=name_of(user), balances=lines), give_resources(user.id))


async def _prompt(callback: CallbackQuery, state: FSMContext, user_id: int, kind: str, text: str, back: str, **data) -> None:
    await state.set_state(AdminGiveStates.waiting_input)
    await state.update_data(uid=user_id, kind=kind, **data)
    await edit_screen(callback, text, cancel_to(back))


@router.callback_query(F.data.startswith(CB_GIVE_RES_PICK))
async def cb_resource_pick(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_GIVE):
        return
    code, _, raw_uid = callback.data.removeprefix(CB_GIVE_RES_PICK).partition(":")
    user = await load_target(callback, session, int(raw_uid) if raw_uid.isdigit() else None)
    if user is None or code not in RESOURCES:
        await callback.answer()
        return
    balance = await resource.balance(session, user.id, code)
    await _prompt(
        callback, state, user.id, GIVE_KIND_RESOURCE,
        t.GIVE_RES_PROMPT.format(label=resource_label(code), name=name_of(user), balance=amount_label(code, balance)),
        f"{CB_GIVE_RES_LIST}{user.id}", code=code,
    )


@router.callback_query(F.data.startswith(CB_GIVE_STATIST))
async def cb_statist(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_GIVE):
        return
    user = await load_target(callback, session, parse_id(callback.data, CB_GIVE_STATIST))
    if user is not None:
        await _prompt(callback, state, user.id, GIVE_KIND_STATIST,
                      t.GIVE_STATIST_PROMPT.format(name=name_of(user), ranks=_RANKS_HINT), f"{CB_GIVE_MENU}{user.id}")


@router.callback_query(F.data.startswith(CB_GIVE_CARD))
async def cb_card(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_GIVE):
        return
    user = await load_target(callback, session, parse_id(callback.data, CB_GIVE_CARD))
    if user is not None:
        await _prompt(callback, state, user.id, GIVE_KIND_CARD,
                      t.GIVE_CARD_PROMPT.format(name=name_of(user)), f"{CB_GIVE_MENU}{user.id}")


@router.callback_query(F.data.startswith(CB_GIVE_SCROLLS))
async def cb_scrolls(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_GIVE):
        return
    user = await load_target(callback, session, parse_id(callback.data, CB_GIVE_SCROLLS))
    if user is not None:
        balance = await players_admin.skip_scrolls(session, user.id)
        await _prompt(callback, state, user.id, GIVE_KIND_SCROLLS,
                      t.GIVE_SCROLLS_PROMPT.format(name=name_of(user), balance=format_number(balance)), f"{CB_GIVE_MENU}{user.id}")


@router.callback_query(F.data.startswith(CB_GIVE_XP))
async def cb_xp(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_GIVE):
        return
    user = await load_target(callback, session, parse_id(callback.data, CB_GIVE_XP))
    if user is not None:
        balance = await players_admin.bp_xp(session, user.id)
        await session.commit()  # сезон/строка пасса могли создаться при чтении
        await _prompt(callback, state, user.id, GIVE_KIND_XP,
                      t.GIVE_XP_PROMPT.format(name=name_of(user), balance=format_number(balance)), f"{CB_GIVE_MENU}{user.id}")


@router.message(AdminGiveStates.waiting_input)
async def on_input(message: Message, state: FSMContext, session: AsyncSession) -> None:
    admin_id = message.from_user.id
    if not await roles.can(session, admin_id, SECTION_GIVE):
        await state.clear()
        return
    data = await state.get_data()
    uid, kind = data["uid"], data["kind"]
    back = cancel_to(f"{CB_GIVE_MENU}{uid}")
    raw = (message.text or "").strip()
    try:
        notice, audit_action, details = await _apply(session, kind, uid, raw, data)
    except _BadInput as e:
        await message.answer(e.text, reply_markup=back)
        return
    except players_admin.NotEnoughError as e:
        await session.rollback()
        await message.answer(t.GIVE_NOT_ENOUGH.format(have=format_number(e.have)), reply_markup=back)
        return
    await audit.log(session, admin_id, audit_action, uid, details)
    await session.commit()
    await state.clear()
    await reply_card(message, session, uid, notice)


class _BadInput(Exception):
    def __init__(self, text: str) -> None:
        self.text = text


async def _apply(session: AsyncSession, kind: str, uid: int, raw: str, data: dict) -> tuple[str, str, dict]:
    """Выполнить выдачу по виду ввода. → (уведомление, действие аудита, детали). Не коммитит."""
    if kind == GIVE_KIND_RESOURCE:
        code = data["code"]
        delta = _number(raw)
        applied, balance = await players_admin.give_resource(session, uid, code, delta)
        notice = t.DONE_RESOURCE.format(
            label=resource_label(code), sign=sign(applied) if applied else "", amount=format_number(abs(applied)),
            balance=amount_label(code, balance),
        )
        return notice, AUDIT_GIVE_RESOURCE, {"resource": code, "requested": delta, "applied": applied}
    if kind == GIVE_KIND_STATIST:
        parts = raw.split()
        valid = len(parts) == 3 and parts[1].isdigit()
        rank_index = players_admin.parse_rank(parts[0]) if valid else None
        delta = parse_int(parts[2]) if valid else None
        if rank_index is None or delta is None:
            raise _BadInput(t.GIVE_BAD_STATIST.format(ranks=_RANKS_HINT))
        rank, stars = RANK_LADDER[rank_index], int(parts[1])
        await players_admin.give_statist(session, uid, StatistKey(rank, stars), delta)
        notice = t.DONE_STATIST.format(rank=rank, stars=stars, sign=sign(delta), amount=format_number(abs(delta)))
        return notice, AUDIT_GIVE_STATIST, {"rank": rank, "stars": stars, "delta": delta}
    if kind == GIVE_KIND_CARD:
        parts = raw.split()
        code = parts[0].lower() if parts else ""
        delta = parse_int(parts[1]) if len(parts) == 2 else None
        if code not in CARD_BY_CODE:
            near = [c for c in CARD_BY_CODE if code and code in c][:_HINT_LIMIT]
            hint = t.GIVE_CARD_HINT.format(codes=", ".join(f"<code>{c}</code>" for c in near)) if near else ""
            raise _BadInput(t.GIVE_BAD_CARD.format(code=esc(code), hint=hint))
        if delta is None:
            raise _BadInput(t.GIVE_BAD_NUMBER)
        await players_admin.give_card(session, uid, code, delta)
        notice = t.DONE_CARD.format(name=CARD_BY_CODE[code].name, sign=sign(delta), amount=format_number(abs(delta)))
        return notice, AUDIT_GIVE_CARD, {"card": code, "delta": delta}
    delta = _number(raw)
    if kind == GIVE_KIND_SCROLLS:
        balance = await players_admin.add_skip_scrolls(session, uid, delta)
        notice = t.DONE_SCROLLS.format(sign=sign(delta), amount=format_number(abs(delta)), balance=format_number(balance))
        return notice, AUDIT_GIVE_SCROLLS, {"delta": delta}
    balance = await players_admin.add_bp_xp(session, uid, delta)
    notice = t.DONE_XP.format(sign=sign(delta), amount=format_number(abs(delta)), balance=format_number(balance))
    return notice, AUDIT_GIVE_BP_XP, {"delta": delta}


def _number(raw: str) -> int:
    value = parse_int(raw)
    if value is None:
        raise _BadInput(t.GIVE_BAD_NUMBER)
    return value
