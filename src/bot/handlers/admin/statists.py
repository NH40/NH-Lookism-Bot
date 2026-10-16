"""Админка → карточка игрока: статисты кнопками и фаза игрока (хендлеры).

Пользователь 2026-10-13: «в админ-панели более лёгкую выдачу и возможность забрать статистов»,
«быстро перекидывать игроков по стадиям». Статисты — раздел «Выдача» (как старая выдача текстом,
она осталась кнопкой «✏️ Вручную»), фаза — раздел «Развитие». Каждое действие — в аудит.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin import SECTION_DEV, SECTION_GIVE
from bot.constant.admin.players_admin import (
    AST_ADD_AMOUNTS,
    AST_GIVE_AMOUNTS,
    AST_RANKS_PER_PAGE,
    AST_TAKE_PERCENTS,
    AUDIT_GIVE_STATIST,
    AUDIT_PHASE,
    AUDIT_WIPE_STATISTS,
    CB_ADMIN_PHASE,
    CB_AST_ADD,
    CB_AST_GIVE,
    CB_AST_MENU,
    CB_AST_RANKS,
    CB_AST_SQUAD,
    CB_AST_TAKE,
    CB_AST_WIPE,
    CB_AST_WIPE_ASK,
    CB_GIVE_MENU,
    CB_GIVE_STATIST,
)
from bot.constant.characteristic import RANK_LADDER
from bot.constant.phase import PHASE_ORDER as PHASES
from bot.handlers.admin.common import guard
from bot.handlers.admin.player_target import load_target, name_of
from bot.services.admin import audit, players_admin
from bot.services.extra import get_army_stats, list_squads
from bot.services.resource.statists import StatistKey, give_statists, take_statists
from bot.texts.admin import players_admin as t
from bot.texts.gang import squad_title
from bot.texts.profile import PHASE_LABELS
from bot.utils.formatting import format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_statists")
_SHOW = 12


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _split(data: str, prefix: str, n: int) -> list[str] | None:
    """`prefix` + n полей + `:uid` — ключ отряда сам содержит «:», поэтому режем с краёв."""
    raw = data.removeprefix(prefix)
    head = raw.split(":", n) if n else [raw]
    return head if len(head) == n + 1 or (n == 0) else None


async def _target(callback: CallbackQuery, session: AsyncSession, section: str, uid_raw: str):
    if not await guard(callback, session, section):
        return None
    return await load_target(callback, session, int(uid_raw) if uid_raw.isdigit() else None)


def _title(k: StatistKey) -> str:
    return squad_title(k.rank, k.stars, k.training_level, k.school, k.school_level)


async def _menu(callback: CallbackQuery, session: AsyncSession, user) -> None:
    squads = await list_squads(session, user.id)
    army = await get_army_stats(session, user.id)
    shown = squads[:_SHOW]
    lines = "\n".join(
        t.AST_SQUAD_LINE.format(title=squad_title(s.rank, s.stars, s.training_level, s.school, s.school_level), qty=format_number(s.total))
        for s in shown
    ) or t.AST_NONE
    if len(squads) > _SHOW:
        lines += t.AST_MORE.format(n=len(squads) - _SHOW)
    text = t.AST_SCREEN.format(
        name=name_of(user), total=format_number(army.total_quantity - army.cards_quantity),
        attack=format_number(army.attack.quantity), defense=format_number(army.defense.quantity), squads=lines,
    )
    rows = [
        [_btn(t.BTN_AST_SQUAD.format(title=squad_title(s.rank, s.stars, s.training_level, s.school, s.school_level), qty=format_number(s.total)),
              f"{CB_AST_SQUAD}{StatistKey(s.rank, s.stars, s.training_level, s.school, s.school_level).encode()}:{user.id}")]
        for s in shown
    ]
    rows.append([_btn(t.BTN_AST_GIVE, f"{CB_AST_RANKS}0:{user.id}"), _btn(t.BTN_AST_MANUAL, f"{CB_GIVE_STATIST}{user.id}")])
    if squads:
        rows.append([_btn(t.BTN_AST_WIPE, f"{CB_AST_WIPE_ASK}{user.id}")])
    rows.append([_btn(t.BTN_BACK, f"{CB_GIVE_MENU}{user.id}")])
    await safe_edit_text(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith(CB_AST_MENU))
async def cb_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await _target(callback, session, SECTION_GIVE, callback.data.removeprefix(CB_AST_MENU))
    if user is None:
        return
    await callback.answer()
    await _menu(callback, session, user)


def _key_uid(raw: str) -> tuple[StatistKey, str] | None:
    """«ранг:зв:ур:школа:ур:uid» → (ключ, uid)."""
    parts = raw.split(":")
    if len(parts) != 6:
        return None
    try:
        return StatistKey.decode(":".join(parts[:5])), parts[5]
    except ValueError:
        return None


async def _squad(callback: CallbackQuery, session: AsyncSession, user, key: StatistKey) -> None:
    sq = next((s for s in await list_squads(session, user.id)
               if (s.rank, s.stars, s.training_level, s.school, s.school_level) == (key.rank, key.stars, key.training_level, key.school, key.school_level)), None)
    if sq is None:
        await _menu(callback, session, user)
        return
    enc = key.encode()
    text = t.AST_SQUAD_SCREEN.format(title=_title(key), name=name_of(user), total=format_number(sq.total),
                                     attack=format_number(sq.attack), defense=format_number(sq.defense))
    rows = [
        [_btn(t.BTN_AST_TAKE.format(label=t.AST_ALL if p == 100 else f"{p}%"), f"{CB_AST_TAKE}{p}:{enc}:{user.id}") for p in AST_TAKE_PERCENTS],
        [_btn(t.BTN_AST_ADD.format(n=format_number(n)), f"{CB_AST_ADD}{n}:{enc}:{user.id}") for n in AST_ADD_AMOUNTS],
        [_btn(t.BTN_BACK, f"{CB_AST_MENU}{user.id}")],
    ]
    await safe_edit_text(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith(CB_AST_SQUAD))
async def cb_squad(callback: CallbackQuery, session: AsyncSession) -> None:
    parsed = _key_uid(callback.data.removeprefix(CB_AST_SQUAD))
    if parsed is None:
        await callback.answer()
        return
    user = await _target(callback, session, SECTION_GIVE, parsed[1])
    if user is None:
        return
    await callback.answer()
    await _squad(callback, session, user, parsed[0])


@router.callback_query(F.data.startswith(CB_AST_TAKE))
async def cb_take(callback: CallbackQuery, session: AsyncSession) -> None:
    pct_raw, _, rest = callback.data.removeprefix(CB_AST_TAKE).partition(":")
    parsed = _key_uid(rest)
    if parsed is None or not pct_raw.isdigit() or int(pct_raw) not in AST_TAKE_PERCENTS:
        await callback.answer()
        return
    user = await _target(callback, session, SECTION_GIVE, parsed[1])
    if user is None:
        return
    key = parsed[0]
    sq = next((s for s in await list_squads(session, user.id)
               if (s.rank, s.stars, s.training_level, s.school, s.school_level) == (key.rank, key.stars, key.training_level, key.school, key.school_level)), None)
    pct = int(pct_raw)
    n = (sq.total if pct == 100 else sq.total * pct // 100) if sq else 0
    if n <= 0 or not await take_statists(session, user.id, key, n):
        await session.rollback()
        await callback.answer(t.AST_NOTHING, show_alert=True)
        return
    await audit.log(session, callback.from_user.id, AUDIT_GIVE_STATIST, user.id, {"key": key.encode(), "delta": -n})
    await session.commit()
    await callback.answer(t.AST_DONE_TAKE.format(n=format_number(n), title=_title(key)))
    await _squad(callback, session, user, key)


@router.callback_query(F.data.startswith(CB_AST_ADD))
async def cb_add(callback: CallbackQuery, session: AsyncSession) -> None:
    n_raw, _, rest = callback.data.removeprefix(CB_AST_ADD).partition(":")
    parsed = _key_uid(rest)
    if parsed is None or not n_raw.isdigit() or int(n_raw) not in AST_ADD_AMOUNTS:
        await callback.answer()
        return
    user = await _target(callback, session, SECTION_GIVE, parsed[1])
    if user is None:
        return
    n, key = int(n_raw), parsed[0]
    await give_statists(session, user.id, key, n)
    await audit.log(session, callback.from_user.id, AUDIT_GIVE_STATIST, user.id, {"key": key.encode(), "delta": n})
    await session.commit()
    await callback.answer(t.AST_DONE_ADD.format(n=format_number(n), title=_title(key)))
    await _squad(callback, session, user, key)


@router.callback_query(F.data.startswith(CB_AST_RANKS))
async def cb_ranks(callback: CallbackQuery, session: AsyncSession) -> None:
    page_raw, _, uid_raw = callback.data.removeprefix(CB_AST_RANKS).partition(":")
    user = await _target(callback, session, SECTION_GIVE, uid_raw)
    if user is None:
        return
    pages = (len(RANK_LADDER) + AST_RANKS_PER_PAGE - 1) // AST_RANKS_PER_PAGE
    page = max(0, min(int(page_raw) if page_raw.isdigit() else 0, pages - 1))
    chunk = RANK_LADDER[page * AST_RANKS_PER_PAGE:(page + 1) * AST_RANKS_PER_PAGE]
    buttons = [_btn(r, f"{CB_AST_GIVE}{r}:0:{user.id}") for r in chunk]
    rows = [buttons[i:i + 5] for i in range(0, len(buttons), 5)]
    nav = []
    if page > 0:
        nav.append(_btn("◀️", f"{CB_AST_RANKS}{page - 1}:{user.id}"))
    nav.append(_btn(f"{page + 1}/{pages}", f"{CB_AST_RANKS}{page}:{user.id}"))
    if page < pages - 1:
        nav.append(_btn("▶️", f"{CB_AST_RANKS}{page + 1}:{user.id}"))
    rows.append(nav)
    rows.append([_btn(t.BTN_BACK, f"{CB_AST_MENU}{user.id}")])
    await callback.answer()
    await safe_edit_text(callback.message, t.AST_RANKS_SCREEN.format(name=name_of(user)), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith(CB_AST_GIVE))
async def cb_give(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.removeprefix(CB_AST_GIVE).split(":")
    if len(parts) != 3 or parts[0] not in RANK_LADDER or not parts[1].isdigit():
        await callback.answer()
        return
    rank, n = parts[0], int(parts[1])
    user = await _target(callback, session, SECTION_GIVE, parts[2])
    if user is None:
        return
    if n == 0 or n not in AST_GIVE_AMOUNTS:
        buttons = [_btn(t.BTN_AST_ADD.format(n=format_number(a)), f"{CB_AST_GIVE}{rank}:{a}:{user.id}") for a in AST_GIVE_AMOUNTS]
        rows = [buttons[:3], buttons[3:], [_btn(t.BTN_BACK, f"{CB_AST_RANKS}0:{user.id}")]]
        await callback.answer()
        await safe_edit_text(callback.message, t.AST_AMOUNT_SCREEN.format(rank=rank, name=name_of(user)),
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        return
    key = StatistKey(rank, 0)
    await give_statists(session, user.id, key, n)
    await audit.log(session, callback.from_user.id, AUDIT_GIVE_STATIST, user.id, {"key": key.encode(), "delta": n})
    await session.commit()
    await callback.answer(t.AST_DONE_ADD.format(n=format_number(n), title=rank))
    await _menu(callback, session, user)


@router.callback_query(F.data.startswith(CB_AST_WIPE_ASK))
async def cb_wipe_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await _target(callback, session, SECTION_GIVE, callback.data.removeprefix(CB_AST_WIPE_ASK))
    if user is None:
        return
    army = await get_army_stats(session, user.id)
    rows = [[_btn(t.BTN_AST_WIPE_YES, f"{CB_AST_WIPE}{user.id}")], [_btn(t.BTN_BACK, f"{CB_AST_MENU}{user.id}")]]
    await callback.answer()
    await safe_edit_text(callback.message, t.AST_WIPE_ASK.format(name=name_of(user), total=format_number(army.total_quantity - army.cards_quantity)),
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith(CB_AST_WIPE))
async def cb_wipe(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await _target(callback, session, SECTION_GIVE, callback.data.removeprefix(CB_AST_WIPE))
    if user is None:
        return
    n = await players_admin.wipe_statists(session, user.id)
    await audit.log(session, callback.from_user.id, AUDIT_WIPE_STATISTS, user.id, {"removed": n})
    await session.commit()
    await callback.answer(t.AST_DONE_WIPE.format(n=format_number(n)), show_alert=True)
    await _menu(callback, session, user)


@router.callback_query(F.data.startswith(CB_ADMIN_PHASE))
async def cb_phase(callback: CallbackQuery, session: AsyncSession) -> None:
    phase, _, uid_raw = callback.data.removeprefix(CB_ADMIN_PHASE).partition(":")
    if phase not in PHASES:
        await callback.answer()
        return
    user = await _target(callback, session, SECTION_DEV, uid_raw)
    if user is None:
        return
    try:
        await players_admin.set_phase(session, user.id, phase)
    except players_admin.EmperorTakenError:
        await session.rollback()
        await callback.answer(t.PHASE_EMPEROR_TAKEN, show_alert=True)
        return
    await audit.log(session, callback.from_user.id, AUDIT_PHASE, user.id, {"phase": phase})
    await session.commit()
    await callback.answer(t.PHASE_DONE.format(label=PHASE_LABELS.get(phase, phase)))
    from bot.handlers.admin.players import render_card

    rendered = await render_card(session, callback.from_user.id, user.id)
    if rendered:
        await safe_edit_text(callback.message, rendered[0], reply_markup=rendered[1])
