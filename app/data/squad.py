from dataclasses import dataclass


@dataclass
class RankConfig:
    rank: str
    emoji: str
    base_power: int
    min_influence: int
    recruit_cost: int


RANKS: list[RankConfig] = [
    RankConfig("E", "⬜", 100,    0,    10),
    RankConfig("D", "🟦", 500,   0,    300),
    RankConfig("C", "🟩", 800,   0,    500),
    RankConfig("B", "🟨", 1200,   0,    1000),
    RankConfig("A", "🟧", 2000,  0,    1500),
    RankConfig("S", "🟥", 4200,  0,    3000),
]

RANKS_BY_ID: dict[str, RankConfig] = {r.rank: r for r in RANKS}

PHASE_RANKS: dict[str, list[str]] = {
    "gang":     ["E", "D", "C", "B"],
    "king":     ["C", "B", "A", "S"],
    "fist":     ["B", "A", "S"],
    "emperor":  ["B", "A", "S"],
}

ATTACK_WIN_INFLUENCE_BONUS: dict[str, int] = {
    "gang":    15,
    "king":    50,
    "fist":    150,
    "emperor": 0,
}

# Бонус к боевой мощи статиста за каждую звезду (+10% за звезду)
STAR_BONUS_PERCENT: dict[int, int] = {
    0: 0,
    1: 10,
    2: 20,
    3: 30,
    4: 40,
    5: 50,
}