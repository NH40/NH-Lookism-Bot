import asyncio
import html

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.utils.formatters import fmt_num, phase_label
from ._common import _get_top_cached, _get_players_page_cached, _phase_emoji, PAGE_SIZE

router = Router()


# ── /top ─────────────────────────────────────────────────────────────────────

@router.message(Command("top"))
async def cmd_top(message: Message, session: AsyncSession, user: User):
    from app.repositories.user_repo import user_repo
    top, my_rank = await asyncio.gather(
        _get_top_cached(session),
        user_repo.get_rank_by_power(session, user.id),
    )

    lines  = ["🏆 <b>Топ-10 игроков по боевой мощи</b>\n"]
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    for i, u in enumerate(top):
        medal = medals.get(i, f"{i + 1}.")
        vvip  = " 👑" if u.ultra_instinct else ""
        lines.append(
            f"{medal} <b>{html.escape(u.full_name)}</b>{vvip}\n"
            f"   💪 {fmt_num(u.combat_power)} | "
            f"{_phase_emoji(u.phase)} {phase_label(u.phase)}"
        )
    lines.append(f"\n📍 Твоё место: #{my_rank}")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Все игроки", callback_data="players_page:0"))
    await message.answer("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")


# ── /players ─────────────────────────────────────────────────────────────────

@router.message(Command("players"))
async def cmd_players(message: Message, session: AsyncSession, user: User):
    await _show_players_page(message, session, user, page=0, edit=False)


async def _show_players_page(message, session: AsyncSession, user: User, page: int, edit: bool = True) -> None:
    players, total = await _get_players_page_cached(session, page)

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start_rank = page * PAGE_SIZE + 1
    lines = [f"👥 <b>Все игроки</b> (стр. {page + 1}/{total_pages}, всего {total})\n"]
    for i, p in enumerate(players):
        rank_num = start_rank + i
        is_me    = " ← ты" if p.id == user.id else ""
        vvip     = " 👑" if p.ultra_instinct else ""
        lines.append(
            f"<b>#{rank_num}</b> {html.escape(p.full_name)}{vvip}{is_me}\n"
            f"  {_phase_emoji(p.phase)} {phase_label(p.phase)} | "
            f"💪 {fmt_num(p.combat_power)}"
        )

    text = "\n".join(lines)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"players_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop_players"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"players_page:{page + 1}"))

    builder = InlineKeyboardBuilder()
    builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🏆 Топ-10", callback_data="show_top"))

    if edit:
        try:
            await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            pass
    else:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("players_page:"))
async def cb_players_page(cb: CallbackQuery, session: AsyncSession, user: User):
    page = int(cb.data.split(":")[1])
    await _show_players_page(cb.message, session, user, page=page, edit=True)
    await cb.answer()


@router.callback_query(F.data == "noop_players")
async def cb_noop_players(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data == "show_top")
async def cb_show_top(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.repositories.user_repo import user_repo
    top, my_rank = await asyncio.gather(
        _get_top_cached(session),
        user_repo.get_rank_by_power(session, user.id),
    )

    lines  = ["🏆 <b>Топ-10 по боевой мощи</b>\n"]
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    for i, u in enumerate(top):
        medal = medals.get(i, f"{i + 1}.")
        vvip  = " 👑" if u.ultra_instinct else ""
        lines.append(
            f"{medal} <b>{html.escape(u.full_name)}</b>{vvip}\n"
            f"   💪 {fmt_num(u.combat_power)} | "
            f"{_phase_emoji(u.phase)} {phase_label(u.phase)}"
        )
    lines.append(f"\n📍 Твоё место: #{my_rank}")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Все игроки", callback_data="players_page:0"))
    try:
        await cb.message.edit_text("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()
