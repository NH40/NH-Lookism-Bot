"""Текстовое представление стола/раздачи покера (общее для хендлера и планировщика)."""
import json
from app.models.poker import PokerTable, PokerPlayer
from app.services.bank.casino.poker_engine import format_cards, hand_name, evaluate_hand
from app.utils.formatters import fmt_num

ROUND_LABELS = {
    "preflop": "Префлоп", "flop": "Флоп", "turn": "Тёрн", "river": "Ривер", "showdown": "Шоудаун",
}
REVEAL_COUNT = {"preflop": 0, "flop": 3, "turn": 4, "river": 5, "showdown": 5}

STATUS_ICON = {"folded": "❌ ", "all_in": "🟡 ", "active": ""}

HAND_RANKING_GUIDE = (
    "📖 <b>Комбинации покера — от старшей к младшей</b>\n\n"
    "🥇 <b>Стрит-флэш</b> — 5 карт по порядку одной масти\n"
    "🥈 <b>Каре</b> — 4 карты одного ранга\n"
    "🥉 <b>Фулл-хаус</b> — тройка + пара\n"
    "🃏 <b>Флэш</b> — 5 карт одной масти вразнобой\n"
    "🔢 <b>Стрит</b> — 5 карт по порядку, масти разные\n"
    "3️⃣ <b>Сет</b> — 3 карты одного ранга\n"
    "2️⃣ <b>Две пары</b> — две пары разных рангов\n"
    "1️⃣ <b>Пара</b> — 2 карты одного ранга\n"
    "🔺 <b>Старшая карта</b> — ничего из вышеперечисленного\n\n"
    "<i>Ваша лучшая комбинация всегда собирается из 5 карт — любых 2 карманных "
    "+ 5 общих на столе. Живая подсказка вашей текущей комбинации показывается "
    "прямо у стола, начиная с флопа.</i>"
)


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


def render_seats(table: PokerTable, players: list[PokerPlayer], users_by_id: dict, viewer_id: int | None = None) -> str:
    lines = []
    for p in sorted(players, key=lambda x: x.seat_index):
        name = _display_name(users_by_id.get(p.user_id))
        if viewer_id is not None and p.user_id == viewer_id:
            name = f"<b>{name} (вы)</b>"
        marker = "▶️ " if (table.status == "active" and p.seat_index == table.current_seat) else "• "
        icon = STATUS_ICON.get(p.status, "")
        leaving_icon = "🚪 " if p.leaving else ""
        lines.append(f"{marker}{icon}{leaving_icon}{name} — стек {fmt_num(p.stack)} (в банке {fmt_num(p.current_round_bet)})")
    return "\n".join(lines)


def render_action_prompt(table: PokerTable, actor: PokerPlayer) -> str:
    to_call = table.current_bet - actor.current_round_bet
    if to_call > 0:
        return f"🎯 Ваш ход. Чтобы уравнять: <b>{fmt_num(to_call)}</b> NHCoin (в банке у вас {fmt_num(actor.current_round_bet)})."
    return "🎯 Ваш ход. Ставок в этом круге нет — можно чекнуть."

def render_hole_cards(player: PokerPlayer) -> str:
    cards = json.loads(player.hole_cards or "[]")
    return format_cards(cards) if cards else "—"


def render_your_combo_line(player: PokerPlayer, table: PokerTable) -> str:
    """Живая подсказка собранной комбинации по открытым на столе картам —
    доступна с флопа (нужно минимум 5 карт: 2 карманные + 3 общие)."""
    if player.status == "folded":
        return ""
    hole = json.loads(player.hole_cards or "[]")
    community = visible_community(table)
    all_cards = hole + community
    if len(all_cards) < 5:
        return ""
    rank = evaluate_hand(all_cards)
    return f"\n🏆 Ваша комбинация: <b>{hand_name(rank)}</b>"


def render_hand_result(
    table_id: int, seat_order: list[int], snapshot: dict, users_by_id: dict,
    hands: dict, net_changes: dict, pot: int, community_cards_json: str,
    viewer_id: int | None = None,
) -> str:
    """snapshot: {user_id: {"status": str, "hole_cards": json str}} — состояние
    ИМЕННО этой раздачи, застывшее до того, как за столом могла начаться
    следующая (см. комментарий в poker_service._finish_hand)."""
    community = json.loads(community_cards_json or "[]")
    lines = [f"🂡 <b>Стол #{table_id} — раздача завершена</b>\n"]
    if community:
        lines.append(f"Общие карты: {format_cards(community)}\n")

    for user_id in seat_order:
        snap = snapshot.get(user_id, {})
        is_viewer = viewer_id is not None and user_id == viewer_id
        name = _display_name(users_by_id.get(user_id))
        if is_viewer:
            name = f"<b>{name} (вы)</b>"
        net = net_changes.get(user_id, 0)
        net_str = f"+{fmt_num(net)}" if net >= 0 else fmt_num(net)

        if snap.get("status") == "folded":
            lines.append(f"❌ {name} — сброс карт ({net_str} NHCoin)")
            continue

        cards_str = format_cards(json.loads(snap.get("hole_cards") or "[]")) or "—"
        rank = hands.get(user_id)
        rank_str = f" — <b>{hand_name(rank)}</b>" if rank else ""
        marker = "👉 " if is_viewer else "🃏 "
        lines.append(f"{marker}{name}: {cards_str}{rank_str} ({net_str} NHCoin)")

    lines.append(f"\n<i>Банк раздачи: {fmt_num(pot)} NHCoin</i>")

    return "\n".join(lines)
