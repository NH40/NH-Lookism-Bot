"""PvP-покер — чистая логика (колода, сила руки, побочные банки, вскрытие). Без БД.
Перенос из 1.0 (`app/services/bank/casino/poker_engine.py`)."""
from __future__ import annotations

import random
from collections import Counter
from itertools import combinations

Card = tuple[int, int]  # (ранг 2..14, масть 0..3)

RANK_NAMES = {11: "J", 12: "Q", 13: "K", 14: "A"}
SUITS = ("♠", "♥", "♦", "♣")


def format_card(card) -> str:
    rank, suit = card
    return f"{RANK_NAMES.get(rank, str(rank))}{SUITS[suit]}"


def format_cards(cards) -> str:
    return " ".join(format_card(c) for c in cards)


def new_deck(rng: random.Random | None = None) -> list[Card]:
    deck = [(rank, suit) for rank in range(2, 15) for suit in range(4)]
    (rng or random).shuffle(deck)
    return deck


def _evaluate_5(cards: list[Card]) -> tuple:
    ranks = sorted((c[0] for c in cards), reverse=True)
    is_flush = len({c[1] for c in cards}) == 1
    unique = sorted(set(ranks), reverse=True)
    straight_high = None
    if len(unique) == 5 and unique[0] - unique[4] == 4:
        straight_high = unique[0]
    elif set(unique) == {14, 5, 4, 3, 2}:
        straight_high = 5  # колесо A-2-3-4-5
    ordered = sorted(Counter(ranks).items(), key=lambda kv: (-kv[1], -kv[0]))
    pattern = [c for _, c in ordered]
    by_count = [r for r, _ in ordered]
    if straight_high and is_flush:
        return (8, straight_high)
    if pattern[0] == 4:
        return (7, by_count[0], by_count[1])
    if pattern[0] == 3 and pattern[1] == 2:
        return (6, by_count[0], by_count[1])
    if is_flush:
        return (5, *ranks)
    if straight_high:
        return (4, straight_high)
    if pattern[0] == 3:
        return (3, by_count[0], *by_count[1:3])
    if pattern[0] == 2 and pattern[1] == 2:
        return (2, by_count[0], by_count[1], by_count[2])
    if pattern[0] == 2:
        return (1, by_count[0], *by_count[1:4])
    return (0, *ranks)


def evaluate(cards) -> tuple:
    """Лучшая пятёрка из 5–7 карт."""
    cards = [tuple(c) for c in cards]
    if len(cards) <= 5:
        return _evaluate_5(cards)
    return max(_evaluate_5(list(combo)) for combo in combinations(cards, 5))


def side_pots(players: list[dict]) -> list[dict]:
    """[{'user_id', 'total_bet', 'folded'}] → слои банка [{'amount', 'eligible': [user_id]}]."""
    contributors = [p for p in players if p["total_bet"] > 0]
    pots, prev, carry = [], 0, 0
    for level in sorted({p["total_bet"] for p in contributors}):
        amount = sum(min(p["total_bet"], level) - prev for p in contributors if p["total_bet"] > prev)
        eligible = [p["user_id"] for p in contributors if not p["folded"] and p["total_bet"] >= level]
        if eligible:
            pots.append({"amount": amount + carry, "eligible": eligible})
            carry = 0
        else:
            # Слой, где все претенденты сбросили (в 1.0 эти деньги пропадали), — в соседний банк.
            carry += amount
        prev = level
    if carry and pots:
        pots[-1]["amount"] += carry
    return pots


def showdown(players: list[dict], community: list, rake_percent: float) -> dict:
    """[{'user_id', 'hole', 'total_bet', 'folded'}] → {'payouts', 'hands', 'rake'}. Рейк — с
    каждого слоя банка до раздела (незаметно для игроков, как в 1.0)."""
    hands = {p["user_id"]: evaluate(list(p["hole"]) + list(community)) for p in players if not p["folded"]}
    payouts = {p["user_id"]: 0 for p in players}
    total_rake = 0
    for pot in side_pots(players):
        rake = int(pot["amount"] * rake_percent)
        total_rake += rake
        best = max(hands[uid] for uid in pot["eligible"])
        winners = [uid for uid in pot["eligible"] if hands[uid] == best]
        share, remainder = divmod(pot["amount"] - rake, len(winners))
        for i, uid in enumerate(winners):
            payouts[uid] += share + (remainder if i == 0 else 0)
    return {"payouts": payouts, "hands": hands, "rake": total_rake}
