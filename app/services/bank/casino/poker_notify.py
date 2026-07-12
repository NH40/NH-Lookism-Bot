"""Рассылка обновлений покерного стола игрокам (общее для хендлера и планировщика)."""
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.poker import PokerTable, PokerPlayer
from app.services.bank.casino.poker_render import (
    render_table_header, render_seats, render_action_prompt, render_hole_cards, render_hand_result,
)


def _display_name(u: User | None) -> str:
    if not u:
        return "Игрок"
    return u.username or u.full_name


def _action_kb(table_id: int, table: PokerTable, actor: PokerPlayer) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    to_call = table.current_bet - actor.current_round_bet
    if to_call > 0:
        builder.row(
            InlineKeyboardButton(text="❌ Сброс", callback_data=f"poker_act:{table_id}:fold"),
            InlineKeyboardButton(text=f"✅ Колл ({to_call})", callback_data=f"poker_act:{table_id}:call"),
        )
    else:
        builder.row(
            InlineKeyboardButton(text="❌ Сброс", callback_data=f"poker_act:{table_id}:fold"),
            InlineKeyboardButton(text="✅ Чек", callback_data=f"poker_act:{table_id}:check"),
        )
    builder.row(InlineKeyboardButton(text="💰 Рейз / Ва-банк", callback_data=f"poker_bet_menu:{table_id}"))
    return builder.as_markup()


async def users_by_id(session: AsyncSession, players: list[PokerPlayer]) -> dict[int, User]:
    ids = [p.user_id for p in players]
    if not ids:
        return {}
    result = await session.execute(select(User).where(User.id.in_(ids)))
    return {u.id: u for u in result.scalars().all()}


async def notify_event(bot: Bot, session: AsyncSession, event: dict) -> None:
    table: PokerTable = event["table"]
    players: list[PokerPlayer] = event["players"]
    ev = event["event"]
    users = await users_by_id(session, players)

    if ev in ("hand_started", "street"):
        current_actor = next((pp for pp in players if pp.seat_index == table.current_seat), None)
        actor_name = _display_name(users.get(current_actor.user_id)) if current_actor else "?"

        for p in players:
            u = users.get(p.user_id)
            if not u or p.status == "folded":
                continue
            header = render_table_header(table)
            seats = render_seats(table, players, users)
            hole = render_hole_cards(p)
            text = f"{header}\n\n{seats}\n\nВаши карты: {hole}"

            is_turn = table.status == "active" and p.seat_index == table.current_seat and p.status == "active"
            if is_turn:
                text += "\n\n" + render_action_prompt(table, p)
                kb = _action_kb(table.id, table, p)
            else:
                text += f"\n\n⏳ Ход: {actor_name}"
                kb = None
            try:
                await bot.send_message(u.tg_id, text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass

    elif ev == "action_taken":
        p = next((pp for pp in players if pp.seat_index == table.current_seat), None)
        if p:
            u = users.get(p.user_id)
            if u:
                header = render_table_header(table)
                seats = render_seats(table, players, users)
                hole = render_hole_cards(p)
                text = f"{header}\n\n{seats}\n\nВаши карты: {hole}\n\n" + render_action_prompt(table, p)
                kb = _action_kb(table.id, table, p)
                try:
                    await bot.send_message(u.tg_id, text, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    pass

        if event.get("auto"):
            auto_uid = event.get("actor_user_id")
            u = users.get(auto_uid)
            if u:
                label = {"fold": "автосброс (не успели походить)", "check": "автопропуск хода"}.get(event.get("action"), event.get("action"))
                try:
                    await bot.send_message(u.tg_id, f"⌛ {label.capitalize()}.", parse_mode="HTML")
                except Exception:
                    pass

    elif ev == "hand_finished":
        text = render_hand_result(table, players, users, event.get("hands", {}), event.get("net_changes", {}))
        for p in players:
            u = users.get(p.user_id)
            if u:
                try:
                    await bot.send_message(u.tg_id, text, parse_mode="HTML")
                except Exception:
                    pass

    elif ev == "table_cancelled":
        for p in players:
            u = users.get(p.user_id)
            if u:
                try:
                    await bot.send_message(
                        u.tg_id,
                        f"🂡 Стол #{table.id} отменён — не набралось достаточно игроков. Вход возвращён.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
