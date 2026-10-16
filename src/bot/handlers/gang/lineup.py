"""Банда — состав отряда: 9 позиций уников (хендлеры).

raw-notes «Банда»: «В составе есть следующие позиции... на данные позиции можно ставить
только уникальных персонажей». Экран состава → экран позиции (что она делает, кто стоит,
подходящие карты со свободной копией) → поставить / снять. Логика — `services/card`.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.position_skill import card_skill_lines
from bot.texts.position_skill import KIND_LABELS, NO_SKILLS, SKILL_LINE, SKILLS_HEADER
from bot.constant.card import POSITIONS
from bot.constant.gang import (
    CB_GANG_LINEUP,
    CB_GANG_POSITION_CLEAR_PREFIX,
    CB_GANG_POSITION_PREFIX,
    CB_GANG_POSITION_SET_PREFIX,
)
from bot.keyboards.gang import lineup_menu, position_menu
from bot.services.card import (
    NoFreeCopyError,
    PositionEmptyError,
    PositionNotAllowedError,
    UnknownCardError,
    assign_position,
    eligible_for_position,
    get_lineup,
    unassign_position,
)
from bot.services.gang import get_gang
from bot.texts.card import POSITION_DESCRIPTIONS, POSITION_LABELS, card_label
from bot.texts.gang import (
    BTN_POSITION_CLEAR,
    BTN_POSITION_MOVE,
    BTN_POSITION_SET,
    LINEUP_EMPTY_SLOT,
    LINEUP_HEADER,
    LINEUP_LINE,
    POSITION_ALREADY_EMPTY,
    POSITION_BTN,
    POSITION_CHOICES,
    POSITION_CLEARED,
    POSITION_NO_CHOICES,
    POSITION_NO_FREE_COPY,
    POSITION_NOT_ALLOWED,
    POSITION_SCREEN,
    POSITION_SET,
    POSITION_SET_REPLACED,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.formatting import esc, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="gang_lineup")


async def _render_lineup(session: AsyncSession, user_id: int):
    lineup = await get_lineup(session, user_id)
    lines = []
    buttons = []
    for position, card in lineup.items():
        label = card_label(card) if card else LINEUP_EMPTY_SLOT
        lines.append(LINEUP_LINE.format(position=POSITION_LABELS[position], card=esc(label)))
        buttons.append((position, POSITION_BTN.format(position=POSITION_LABELS[position], card=label)))
    return LINEUP_HEADER.format(lines="\n".join(lines)), lineup_menu(buttons)


def _skills_block(card, position: str) -> str:
    """Навыки карты на этой позиции (числа её редкости) — свёрнутой цитатой."""
    if card is None:
        return ""
    lines = card_skill_lines(card, position)
    if not lines:
        return NO_SKILLS + "\n"
    body = "\n".join(SKILL_LINE.format(name=esc(s.name), kind=KIND_LABELS[s.kind], desc=esc(s.text)) for s in lines)
    header = SKILLS_HEADER.format(position=POSITION_LABELS[position], count=len(lines))
    return f"<blockquote expandable>{header}\n{body}</blockquote>\n"


async def _render_position(session: AsyncSession, user_id: int, position: str, page: int):
    current = (await get_lineup(session, user_id))[position]
    choices = await eligible_for_position(session, user_id, position)
    text = POSITION_SCREEN.format(
        position=POSITION_LABELS[position],
        description=POSITION_DESCRIPTIONS[position],
        current=esc(card_label(current)) if current else LINEUP_EMPTY_SLOT,
        skills=_skills_block(current, position),
        choices=POSITION_CHOICES if choices else POSITION_NO_CHOICES,
    )
    markup = position_menu(
        position,
        choices=[
            (
                e.card.code,
                BTN_POSITION_SET.format(label=card_label(e.card), free=format_number(e.army)) if e.army > 0
                else BTN_POSITION_MOVE.format(label=card_label(e.card), from_pos=POSITION_LABELS[e.placed[0]]),
            )
            for e in choices
            if current is None or e.card.code != current.code
        ],
        page=page,
        clear_label=BTN_POSITION_CLEAR.format(card=current.name) if current else None,
    )
    return text, markup


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


@router.callback_query(F.data == CB_GANG_LINEUP)
async def cb_lineup(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    text, markup = await _render_lineup(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_GANG_POSITION_PREFIX))
async def cb_position(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    try:
        position, page_raw = callback.data.removeprefix(CB_GANG_POSITION_PREFIX).split(":")
        page = int(page_raw)
        if position not in POSITIONS:
            raise ValueError(position)
    except ValueError:
        await callback.answer()
        return
    await callback.answer()
    text, markup = await _render_position(session, callback.from_user.id, position, page)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_GANG_POSITION_SET_PREFIX))
async def cb_position_set(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    try:
        position, code = callback.data.removeprefix(CB_GANG_POSITION_SET_PREFIX).split(":", 1)
        replaced = await assign_position(session, callback.from_user.id, position, code)
    except ValueError:
        await callback.answer()
        return
    except (UnknownCardError, PositionNotAllowedError):
        await callback.answer(POSITION_NOT_ALLOWED, show_alert=True)
        return
    except NoFreeCopyError:
        await callback.answer(POSITION_NO_FREE_COPY, show_alert=True)
        return

    current = (await get_lineup(session, callback.from_user.id))[position]
    name = current.name if current else code
    # Popup — без HTML.
    if replaced is not None:
        await callback.answer(POSITION_SET_REPLACED.format(card=name, position=POSITION_LABELS[position], old=replaced.name))
    else:
        await callback.answer(POSITION_SET.format(card=name, position=POSITION_LABELS[position]))
    text, markup = await _render_lineup(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_GANG_POSITION_CLEAR_PREFIX))
async def cb_position_clear(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    position = callback.data.removeprefix(CB_GANG_POSITION_CLEAR_PREFIX)
    if position not in POSITIONS:
        await callback.answer()
        return
    try:
        card = await unassign_position(session, callback.from_user.id, position)
    except PositionEmptyError:
        await callback.answer(POSITION_ALREADY_EMPTY, show_alert=True)
    else:
        await callback.answer(POSITION_CLEARED.format(card=card.name if card else "—"))
    text, markup = await _render_lineup(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)
