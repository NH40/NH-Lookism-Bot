"""Топ игроков/кланов (`/top`) и список всех игроков (`/players`) (хендлеры).

Пользователь 2026-10-11: «Топ и топ кланов с наградами за сезон», «/players — список всех
игроков». Топ — 10 лучших с наградой за место и твоё место; `/players` — все постранично.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.top import PLAYERS_PAGE_SIZE, clan_reward, player_reward
from bot.constant.top import CB_PLAYERS_PAGE_PREFIX, CB_TOP_PREFIX, TAB_CLANS, TAB_PLAYERS
from bot.keyboards.top import players_menu, top_menu
from bot.services.top import TopView, get_players_page, get_top
from bot.texts.profile import PHASE_LABELS
from bot.texts.top import (
    CLAN_ROW,
    EMPTY_ROWS,
    MEDALS,
    NOT_IN_TOP,
    PLAYER_ROW,
    PLAYERS_CLAN,
    PLAYERS_ROW,
    PLAYERS_SCREEN,
    REWARD_SUFFIX,
    SEASON_LINE,
    TOP_CLANS_SCREEN,
    TOP_PLAYERS_SCREEN,
    reward_text,
)
from bot.utils.formatting import esc, format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="top")


def _medal(place: int) -> str:
    return MEDALS.get(place, f"{place}.")


def _reward(parts: tuple[int, int, int]) -> str:
    text = reward_text(*parts)
    return REWARD_SUFFIX.format(reward=text) if text else ""


def _render_top(view: TopView, tab: str) -> str:
    season_line = SEASON_LINE.format(countdown=format_countdown(view.season_ends_in)) if view.season_ends_in else ""
    if tab == TAB_CLANS:
        rows = [
            CLAN_ROW.format(
                medal=_medal(i), name=esc(c.name), lands=format_number(c.lands), members=c.members, reward=_reward(clan_reward(i))
            )
            for i, c in enumerate(view.clans, start=1)
        ]
        return TOP_CLANS_SCREEN.format(rows="\n".join(rows) or EMPTY_ROWS, season_line=season_line)
    rows = [
        PLAYER_ROW.format(medal=_medal(i), name=esc(p.name), power=format_number(p.power), reward=_reward(player_reward(i)))
        for i, p in enumerate(view.players, start=1)
    ]
    return TOP_PLAYERS_SCREEN.format(
        rows="\n".join(rows) or EMPTY_ROWS,
        my_place=f"#{view.my_place}" if view.my_place else NOT_IN_TOP,
        my_power=format_number(view.my_power),
        season_line=season_line,
    )


async def _render_players(session: AsyncSession, page: int) -> tuple[str, object]:
    rows, page, pages, total = await get_players_page(session, page, PLAYERS_PAGE_SIZE)
    start = page * PLAYERS_PAGE_SIZE
    lines = [
        PLAYERS_ROW.format(
            place=start + i, name=esc(p.name), phase=PHASE_LABELS.get(p.phase, p.phase), power=format_number(p.power),
            clan=PLAYERS_CLAN.format(clan=esc(p.clan)) if p.clan else "",
        )
        for i, p in enumerate(rows, start=1)
    ]
    text = PLAYERS_SCREEN.format(total=format_number(total), rows="\n".join(lines) or EMPTY_ROWS)
    return text, players_menu(page, pages)


@router.message(Command("top"))
async def cmd_top(message: Message, session: AsyncSession) -> None:
    view = await get_top(session, message.from_user.id)
    await message.answer(_render_top(view, TAB_PLAYERS), reply_markup=top_menu(TAB_PLAYERS))


@router.callback_query(F.data.startswith(CB_TOP_PREFIX))
async def cb_top(callback: CallbackQuery, session: AsyncSession) -> None:
    tab = callback.data.removeprefix(CB_TOP_PREFIX)
    tab = tab if tab in (TAB_PLAYERS, TAB_CLANS) else TAB_PLAYERS
    await callback.answer()
    view = await get_top(session, callback.from_user.id)
    await safe_edit_text(callback.message, _render_top(view, tab), reply_markup=top_menu(tab))


@router.message(Command("players"))
async def cmd_players(message: Message, session: AsyncSession) -> None:
    text, markup = await _render_players(session, 0)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_PLAYERS_PAGE_PREFIX))
async def cb_players(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        page = int(callback.data.removeprefix(CB_PLAYERS_PAGE_PREFIX))
    except ValueError:
        page = 0
    await callback.answer()
    text, markup = await _render_players(session, page)
    await safe_edit_text(callback.message, text, reply_markup=markup)
