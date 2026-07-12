"""Чистая логика покера: колода, оценка руки, сайд-поты. Без обращений к БД."""
import random
from collections import Counter
from itertools import combinations

RANK_NAMES = {11: "J", 12: "Q", 13: "K", 14: "A"}
SUIT_EMOJI = ["♠", "♥", "♦", "♣"]

HAND_NAMES = {
    8: "Стрит-флэш",
    7: "Каре",
    6: "Фулл-хаус",
    5: "Флэш",
    4: "Стрит",
    3: "Сет",
    2: "Две пары",
    1: "Пара",
    0: "Старшая карта",
}


def format_rank(rank: int) -> str:
    return RANK_NAMES.get(rank, str(rank))


def format_card(card) -> str:
    rank, suit = card
    return f"{format_rank(rank)}{SUIT_EMOJI[suit]}"


def format_cards(cards) -> str:
    return " ".join(format_card(c) for c in cards)


def new_shuffled_deck() -> list[tuple[int, int]]:
    deck = [(rank, suit) for rank in range(2, 15) for suit in range(4)]
    random.shuffle(deck)
    return deck


def _evaluate_5(cards: list[tuple[int, int]]) -> tuple:
    ranks = sorted((c[0] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    is_flush = len(set(suits)) == 1

    unique_ranks = sorted(set(ranks), reverse=True)
    straight_high = None
    if len(unique_ranks) == 5 and unique_ranks[0] - unique_ranks[4] == 4:
        straight_high = unique_ranks[0]
    elif set(unique_ranks) == {14, 5, 4, 3, 2}:
        straight_high = 5  # колесо A-2-3-4-5

    counts = Counter(ranks)
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], -kv[0]))
    pattern = [c for _, c in ordered]
    ordered_ranks = [r for r, _ in ordered]

    if straight_high and is_flush:
        return (8, straight_high)
    if pattern[0] == 4:
        return (7, ordered_ranks[0], ordered_ranks[1])
    if pattern[0] == 3 and pattern[1] == 2:
        return (6, ordered_ranks[0], ordered_ranks[1])
    if is_flush:
        return (5, *ranks)
    if straight_high:
        return (4, straight_high)
    if pattern[0] == 3:
        return (3, ordered_ranks[0], *ordered_ranks[1:3])
    if pattern[0] == 2 and pattern[1] == 2:
        return (2, ordered_ranks[0], ordered_ranks[1], ordered_ranks[2])
    if pattern[0] == 2:
        return (1, ordered_ranks[0], *ordered_ranks[1:4])
    return (0, *ranks)


def evaluate_hand(cards: list[tuple[int, int]]) -> tuple:
    """Лучшая комбинация из 5 карт среди всех сочетаний (карт может быть 5..7)."""
    cards = [tuple(c) for c in cards]
    if len(cards) <= 5:
        return _evaluate_5(cards)
    return max(_evaluate_5(list(combo)) for combo in combinations(cards, 5))


def hand_name(rank_tuple: tuple) -> str:
    return HAND_NAMES.get(rank_tuple[0], "?")


def compute_side_pots(players: list[dict]) -> list[dict]:
    """
    players: [{'user_id': int, 'total_bet': int, 'folded': bool}, ...]
    Возвращает список under-pot слоёв: [{'amount': int, 'eligible': [user_id, ...]}, ...]
    """
    contributors = [p for p in players if p["total_bet"] > 0]
    if not contributors:
        return []
    levels = sorted(set(p["total_bet"] for p in contributors))
    pots = []
    prev = 0
    for level in levels:
        layer_contributors = [p for p in contributors if p["total_bet"] > prev]
        amount = sum(min(p["total_bet"], level) - prev for p in layer_contributors)
        eligible = [p["user_id"] for p in contributors if not p["folded"] and p["total_bet"] >= level]
        if amount > 0 and eligible:
            pots.append({"amount": amount, "eligible": eligible})
        prev = level
    return pots


def resolve_showdown(players: list[dict], community_cards: list, rake_percent: float) -> dict:
    """
    players: [{'user_id': int, 'hole_cards': [[r,s],[r,s]], 'total_bet': int, 'folded': bool}]
    Возвращает {'payouts': {user_id: int}, 'hands': {user_id: rank_tuple}, 'rake_taken': int}.
    Рейк вычитается из каждого под-банка до раздела между победителями — незаметно для игроков.
    """
    pots = compute_side_pots(players)
    hands: dict[int, tuple] = {}
    for p in players:
        if not p["folded"]:
            hands[p["user_id"]] = evaluate_hand(list(p["hole_cards"]) + list(community_cards))

    payouts: dict[int, int] = {p["user_id"]: 0 for p in players}
    total_rake = 0

    for pot in pots:
        eligible = pot["eligible"]
        amount = pot["amount"]
        rake = int(amount * rake_percent)
        total_rake += rake
        distributable = amount - rake

        best_rank = max(hands[uid] for uid in eligible)
        winners = [uid for uid in eligible if hands[uid] == best_rank]
        share = distributable // len(winners)
        remainder = distributable - share * len(winners)
        for i, uid in enumerate(winners):
            payouts[uid] += share + (remainder if i == 0 else 0)

    return {"payouts": payouts, "hands": hands, "rake_taken": total_rake}
