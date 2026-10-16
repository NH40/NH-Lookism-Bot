"""Админка — Развитие игрока (из карточки): пути, техники, гениальности (выдача/уровень/активный),
родословные, второе тело, премиум-пасс, пробуждение, потенциал, ранги характеристик."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.awakening import AWAKENING_MAX
from bot.config.development import MAX_LEVEL
from bot.constant.admin import CB_ADMIN_PLAYER_DEV_PREFIX, SECTION_DEV
from bot.constant.admin.players_admin import (
    AUDIT_DEV_AWAKENING,
    AUDIT_DEV_BLOODLINE,
    AUDIT_DEV_BODY,
    AUDIT_DEV_PASS,
    AUDIT_DEV_POTENTIAL,
    AUDIT_DEV_SET_ACTIVE,
    AUDIT_DEV_SET_LEVEL,
    AUDIT_DEV_STAT,
    BLOOD_NONE,
    BLOOD_SLOTS,
    CB_DEV_ACTIVE,
    CB_DEV_AWAKEN,
    CB_DEV_BLOOD,
    CB_DEV_BLOOD_LEVEL,
    CB_DEV_BLOOD_PICK,
    CB_DEV_BODY,
    CB_DEV_ITEM,
    CB_DEV_LEVEL,
    CB_DEV_LIST,
    CB_DEV_MENU,
    CB_DEV_MISC,
    CB_DEV_PASS,
    CB_DEV_POTENTIAL,
    CB_DEV_STATS,
    CB_DEV_STAT_PICK,
    DEV_KINDS,
)
from bot.constant.characteristic import POTENTIAL_ORDER, RANK_LADDER, STATS
from bot.db.models.user import User
from bot.handlers.admin.common import guard
from bot.handlers.admin.player_target import back_to_card, edit_screen, load_target, name_of, parse_args, reply_card
from bot.keyboards.admin import players_admin as kb
from bot.services.admin import audit, players_admin, roles
from bot.states.admin_players import AdminDevStates
from bot.texts.admin import players_admin as t
from bot.utils.formatting import esc

router = Router(name="admin_dev")


async def _open(callback: CallbackQuery, session: AsyncSession, prefix: str) -> tuple[list[str], User] | None:
    """Права + разбор `callback_data` + цель; None — ответ уже дан."""
    if not await guard(callback, session, SECTION_DEV):
        return None
    parsed = parse_args(callback.data, prefix)
    user = await load_target(callback, session, parsed[1] if parsed else None)
    return (parsed[0], user) if user is not None else None


async def _commit(callback: CallbackQuery, session: AsyncSession, action: str, uid: int, details: dict) -> None:
    await audit.log(session, callback.from_user.id, action, uid, details)
    await session.commit()


def _item(kind: str, idx: int) -> tuple[str, str] | None:
    """(код, название) по индексу в каталоге; None — устаревшая кнопка."""
    codes = t.DEV_CODES.get(kind, ())
    if not 0 <= idx < len(codes):
        return None
    return codes[idx], t.DEV_NAMES[kind].get(codes[idx], codes[idx])


# ------------------------------- меню / списки -------------------------------

@router.callback_query(F.data.startswith(CB_ADMIN_PLAYER_DEV_PREFIX) | F.data.startswith(CB_DEV_MENU))
async def cb_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    prefix = CB_DEV_MENU if callback.data.startswith(CB_DEV_MENU) else CB_ADMIN_PLAYER_DEV_PREFIX
    opened = await _open(callback, session, prefix)
    if opened is None:
        return
    await state.clear()
    user = opened[1]
    await edit_screen(callback, t.DEV_MENU.format(name=name_of(user), summary=""), kb.dev_menu(user.id))


@router.callback_query(F.data.startswith(CB_DEV_LIST))
async def cb_list(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_LIST)
    if opened is None or opened[0][0] not in DEV_KINDS:
        return
    kind, user = opened[0][0], opened[1]
    owned, active = await players_admin.dev_state(session, user.id, kind)
    await edit_screen(
        callback, t.DEV_LIST.format(title=t.DEV_KIND_TITLES[kind], name=name_of(user)), kb.dev_list(user.id, kind, owned, active)
    )


async def _show_item(callback: CallbackQuery, session: AsyncSession, user: User, kind: str, idx: int) -> None:
    item = _item(kind, idx)
    if item is None:
        await callback.answer()
        return
    code, title = item
    owned, active = await players_admin.dev_state(session, user.id, kind)
    status = (
        t.STATUS_OWNED.format(level=owned[code], active=t.STATUS_ACTIVE if code == active else "")
        if code in owned else t.STATUS_NOT_OWNED
    )
    text = t.DEV_ITEM.format(title=esc(title), name=name_of(user), status=status, max=MAX_LEVEL)
    await edit_screen(callback, text, kb.dev_item(user.id, kind, idx, code in owned, code == active))


@router.callback_query(F.data.startswith(CB_DEV_ITEM))
async def cb_item(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_ITEM)
    if opened is None or len(opened[0]) != 2 or not opened[0][1].isdigit():
        return
    await _show_item(callback, session, opened[1], opened[0][0], int(opened[0][1]))


@router.callback_query(F.data.startswith(CB_DEV_LEVEL))
async def cb_level(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_LEVEL)
    if opened is None or len(opened[0]) != 3 or not (opened[0][1].isdigit() and opened[0][2].isdigit()):
        return
    (kind, raw_idx, raw_level), user = opened
    item = _item(kind, int(raw_idx))
    level = int(raw_level)
    if item is None or not 0 <= level <= MAX_LEVEL:
        await callback.answer()
        return
    code, title = item
    await players_admin.set_dev_level(session, user.id, kind, code, level)
    await _commit(callback, session, AUDIT_DEV_SET_LEVEL, user.id, {"kind": kind, "code": code, "level": level})
    notice = (t.DONE_LEVEL if level else t.DONE_TAKEN).format(title=t.DEV_KIND_TITLES[kind], item=title, level=level)
    await back_to_card(callback, session, user.id, notice)


@router.callback_query(F.data.startswith(CB_DEV_ACTIVE))
async def cb_active(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_ACTIVE)
    if opened is None or len(opened[0]) != 2 or not opened[0][1].isdigit():
        return
    (kind, raw_idx), user = opened
    item = _item(kind, int(raw_idx))
    if item is None:
        await callback.answer()
        return
    if not await players_admin.set_dev_active(session, user.id, kind, item[0]):
        await callback.answer(t.NOT_OWNED_ALERT, show_alert=True)
        return
    await _commit(callback, session, AUDIT_DEV_SET_ACTIVE, user.id, {"kind": kind, "code": item[0]})
    await back_to_card(callback, session, user.id, t.DONE_ACTIVE.format(title=t.DEV_KIND_TITLES[kind], item=item[1]))


# --------------------------------- родословные ---------------------------------

def _blood_text(slot: int, user: User, current: str | None, level: int) -> str:
    value = f"{t.BLOODLINE_TITLES.get(current, current)} {level}" if current else "—"
    return t.DEV_BLOOD.format(slot=slot, name=name_of(user), current=value)


@router.callback_query(F.data.startswith(CB_DEV_BLOOD))
async def cb_blood(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_BLOOD)
    if opened is None or len(opened[0]) != 1 or not opened[0][0].isdigit() or int(opened[0][0]) not in BLOOD_SLOTS:
        return
    slot, user = int(opened[0][0]), opened[1]
    current, level = await players_admin.bloodline_state(session, user.id, slot)
    await edit_screen(callback, _blood_text(slot, user, current, level), kb.dev_bloodline(user.id, slot, current))


@router.callback_query(F.data.startswith(CB_DEV_BLOOD_PICK))
async def cb_blood_pick(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_BLOOD_PICK)
    if opened is None or len(opened[0]) != 2 or not all(p.isdigit() for p in opened[0]):
        return
    slot, idx, user = int(opened[0][0]), int(opened[0][1]), opened[1]
    if slot not in BLOOD_SLOTS:
        return
    if idx == BLOOD_NONE:
        code, level = None, 0
    elif 0 <= idx < len(t.BLOODLINE_CODES):
        code = t.BLOODLINE_CODES[idx]
        _, old_level = await players_admin.bloodline_state(session, user.id, slot)
        level = max(old_level, 1)
    else:
        await callback.answer()
        return
    await players_admin.set_bloodline(session, user.id, slot, code, level)
    await _commit(callback, session, AUDIT_DEV_BLOODLINE, user.id, {"slot": slot, "code": code, "level": level})
    notice = t.DONE_BLOOD.format(slot=slot, value=f"{t.BLOODLINE_TITLES.get(code, code)} {level}" if code else "—")
    await back_to_card(callback, session, user.id, notice)


@router.callback_query(F.data.startswith(CB_DEV_BLOOD_LEVEL))
async def cb_blood_level(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_BLOOD_LEVEL)
    if opened is None or len(opened[0]) != 2 or not all(p.isdigit() for p in opened[0]):
        return
    slot, level, user = int(opened[0][0]), int(opened[0][1]), opened[1]
    current, _ = await players_admin.bloodline_state(session, user.id, slot)
    if slot not in BLOOD_SLOTS or current is None or not 1 <= level <= MAX_LEVEL:
        await callback.answer()
        return
    await players_admin.set_bloodline(session, user.id, slot, current, level)
    await _commit(callback, session, AUDIT_DEV_BLOODLINE, user.id, {"slot": slot, "code": current, "level": level})
    await back_to_card(callback, session, user.id, t.DONE_BLOOD.format(slot=slot, value=f"{t.BLOODLINE_TITLES.get(current, current)} {level}"))


# ------------------------------------ прочее ------------------------------------

async def _show_misc(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    body = bool(user.second_body)
    premium = await players_admin.premium_pass(session, user.id)
    await session.commit()  # строка/сезон пасса могли создаться при чтении
    ranks = await players_admin.stat_ranks(session, user.id)
    text = t.DEV_MISC.format(
        name=name_of(user), body=t.YES if body else t.NO, premium=t.YES if premium else t.NO,
        awakening=user.awakening_level, potential=esc(user.potential or "—"),
        stats=", ".join(f"{t.STAT_NAMES[s]} {RANK_LADDER[i]}" for s, i in ranks.items()),
    )
    await edit_screen(callback, text, kb.dev_misc(user.id, body=body, premium=premium))


@router.callback_query(F.data.startswith(CB_DEV_MISC))
async def cb_misc(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_MISC)
    if opened is None:
        return
    await state.clear()
    await session.refresh(opened[1])
    await _show_misc(callback, session, opened[1])


@router.callback_query(F.data.startswith(CB_DEV_BODY))
async def cb_body(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_BODY)
    if opened is None:
        return
    user = opened[1]
    on = await players_admin.toggle_second_body(session, user.id)
    await _commit(callback, session, AUDIT_DEV_BODY, user.id, {"second_body": on})
    await back_to_card(callback, session, user.id, t.DONE_BODY.format(state=t.STATE_ON if on else t.STATE_OFF))


@router.callback_query(F.data.startswith(CB_DEV_PASS))
async def cb_pass(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_PASS)
    if opened is None:
        return
    user = opened[1]
    on = await players_admin.toggle_premium_pass(session, user.id)
    await _commit(callback, session, AUDIT_DEV_PASS, user.id, {"premium": on})
    await back_to_card(callback, session, user.id, t.DONE_PASS.format(state=t.STATE_ON if on else t.STATE_OFF))


@router.callback_query(F.data.startswith(CB_DEV_AWAKEN))
async def cb_awaken(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_AWAKEN)
    if opened is None or len(opened[0]) != 1:
        return
    user = opened[1]
    level = int(opened[0][0]) if opened[0][0].lstrip("-").isdigit() else -1
    if level < 0:  # показать выбор
        await edit_screen(callback, t.DEV_AWAKEN.format(name=name_of(user), current=user.awakening_level), kb.dev_awakening(user.id, AWAKENING_MAX))
        return
    if level > AWAKENING_MAX:
        await callback.answer()
        return
    await players_admin.set_awakening(session, user.id, level)
    await _commit(callback, session, AUDIT_DEV_AWAKENING, user.id, {"level": level})
    await back_to_card(callback, session, user.id, t.DONE_AWAKEN.format(value=level))


@router.callback_query(F.data.startswith(CB_DEV_POTENTIAL))
async def cb_potential(callback: CallbackQuery, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_POTENTIAL)
    if opened is None or len(opened[0]) != 1:
        return
    user = opened[1]
    idx = int(opened[0][0]) if opened[0][0].lstrip("-").isdigit() else -1
    if idx < 0:
        await edit_screen(callback, t.DEV_POTENTIAL.format(name=name_of(user), current=esc(user.potential or "—")), kb.dev_potential(user.id))
        return
    if idx >= len(POTENTIAL_ORDER):
        await callback.answer()
        return
    await players_admin.set_potential(session, user.id, POTENTIAL_ORDER[idx])
    await _commit(callback, session, AUDIT_DEV_POTENTIAL, user.id, {"potential": POTENTIAL_ORDER[idx]})
    await back_to_card(callback, session, user.id, t.DONE_POTENTIAL.format(value=POTENTIAL_ORDER[idx]))


# --------------------------------- характеристики ---------------------------------

@router.callback_query(F.data.startswith(CB_DEV_STATS))
async def cb_stats(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_STATS)
    if opened is None:
        return
    await state.clear()
    user = opened[1]
    ranks = await players_admin.stat_ranks(session, user.id)
    lines = "\n".join(f"{t.STAT_NAMES[s]}: <b>{RANK_LADDER[i]}</b>" for s, i in ranks.items())
    await edit_screen(callback, t.DEV_STATS.format(name=name_of(user), stats=lines), kb.dev_stats(user.id))


@router.callback_query(F.data.startswith(CB_DEV_STAT_PICK))
async def cb_stat_pick(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    opened = await _open(callback, session, CB_DEV_STAT_PICK)
    if opened is None or len(opened[0]) != 1 or opened[0][0] not in STATS:
        return
    stat, user = opened[0][0], opened[1]
    ranks = await players_admin.stat_ranks(session, user.id)
    await state.set_state(AdminDevStates.waiting_rank)
    await state.update_data(uid=user.id, stat=stat)
    text = t.DEV_RANK_PROMPT.format(stat=t.STAT_NAMES[stat], name=name_of(user), current=RANK_LADDER[ranks[stat]], ranks=", ".join(RANK_LADDER))
    await edit_screen(callback, text, kb.cancel_to(f"{CB_DEV_STATS}{user.id}"))


@router.message(AdminDevStates.waiting_rank)
async def on_rank(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_DEV):
        await state.clear()
        return
    data = await state.get_data()
    uid, stat = data["uid"], data["stat"]
    index = players_admin.parse_rank(message.text or "")
    if index is None:
        await message.answer(t.DEV_BAD_RANK.format(ranks=", ".join(RANK_LADDER)), reply_markup=kb.cancel_to(f"{CB_DEV_STATS}{uid}"))
        return
    await players_admin.set_stat_rank(session, uid, stat, index)
    await audit.log(session, message.from_user.id, AUDIT_DEV_STAT, uid, {"stat": stat, "rank": RANK_LADDER[index]})
    await session.commit()
    await state.clear()
    await reply_card(message, session, uid, t.DONE_STAT.format(stat=t.STAT_NAMES[stat], rank=RANK_LADDER[index]))
