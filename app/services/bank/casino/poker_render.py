"""Текстовое представление стола/раздачи покера (общее для хендлера и планировщика)."""
import json
from app.models.poker import PokerTable, PokerPlayer
from app.services.bank.casino.poker_engine import format_cards, hand_name
from app.utils.formatters import fmt_num

ROUND_LABELS = {
    "preflop": "Префлоп", "flop": "Флоп", "turn": "Тёрн", "river": "Ривер", "showdown": "Шоудаун",
}
REVEAL_COUNT = {"preflop": 0, "flop": 3, "turn": 4, "river": 5, "showdown": 5}

STATUS_ICON = {"folded": "❌ ", "all_in": "🟡 ", "active": ""}


def _display_name(u) -> str:
    if not u:
        return "Игрок"
    return u.username or u.full_name


def visible_community(table: PokerTable) -> list:
    cards = json.loads(table.community_cards or "[]")
    return cards[:REVEAL_COUNT.get(table.current_round, 0)]


def render_table_header(table: PokerTable) -> str:
    community = visible_community(table)
    lines = [
        f"🂡 <b>Покер — стол #{table.id}</b> ({ROUND_LABELS.get(table.current_round, table.current_round)})",
        f"Банк: <b>{fmt_num(table.pot)}</b> NHCoin",
        f"Общие карты: {format_cards(community) if community else '—'}",
    ]
    return "\n".join(lines)


def render_seats(table: PokerTable, players: list[PokerPlayer], users_by_id: dict) -> str:
    lines = []
    for p in sorted(players, key=lambda x: x.seat_index):
        name = _display_name(users_by_id.get(p.user_id))
        marker = "▶️ " if (table.status == "active" and p.seat_index == table.current_seat) else "• "
        icon = STATUS_ICON.get(p.status, "")
        lines.append(f"{marker}{icon}{name} — стек {fmt_num(p.stack)} (в банке {fmt_num(p.current_round_bet)})")
    return "\n".join(lines)


def render_action_prompt(table: PokerTable, actor: PokerPlayer) -> str:
    to_call = table.current_bet - actor.current_round_bet
    if to_call > 0:
        return f"🎯 Ваш ход. Чтобы уравнять: <b>{fmt_num(to_call)}</b> NHCoin (в банке у вас {fmt_num(actor.current_round_bet)})."
    return "🎯 Ваш ход. Ставок в этом круге нет — можно чекнуть."

def render_hole_cards(player: PokerPlayer) -> str:
    cards = json.loads(player.hole_cards or "[]")
    return format_cards(cards) if cards else "—"


def render_hand_result(table: PokerTable, players: list[PokerPlayer], users_by_id: dict, hands: dict, net_changes: dict) -> str:
    community = json.loads(table.community_cards or "[]")
    lines = [f"🂡 <b>Стол #{table.id} — раздача завершена</b>\n"]
    if community:
        lines.append(f"Общие карты: {format_cards(community)}\n")

    for p in sorted(players, key=lambda x: x.seat_index):
        name = _display_name(users_by_id.get(p.user_id))
        net = net_changes.get(p.user_id, 0)
        net_str = f"+{fmt_num(net)}" if net >= 0 else fmt_num(net)

        if p.status == "folded":
            lines.append(f"❌ {name} — сброс карт ({net_str} NHCoin)")
            continue

        cards_str = render_hole_cards(p)
        rank = hands.get(p.user_id)
        rank_str = f" — {hand_name(rank)}" if rank else ""
        lines.append(f"🃏 {name}: {cards_str}{rank_str} ({net_str} NHCoin)")

    if table.rake_taken:
        lines.append(f"\n<i>Банк: {fmt_num(table.pot)} NHCoin</i>")

    return "\n".join(lines)
