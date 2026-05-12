from dataclasses import dataclass


@dataclass
class RankConfig:
    rank: str
    emoji: str
    base_power: int
    min_influence: int
    recruit_cost: int


RANKS: list[RankConfig] = [
    RankConfig("F",     "⬛",  10,       0,       5),
    RankConfig("E",     "⬜",  50,       0,      10),
    RankConfig("D",     "🟦",  100,       0,     100),
    RankConfig("C",     "🟩", 250,      0,     250),
    RankConfig("B",     "🟨", 500,      0,   300),
    RankConfig("A",     "🟧", 750,     0,   500),
    RankConfig("S",     "🟥", 1_000,     0,   600),
    RankConfig("SS",    "💠", 1_200,     0,   750),
    RankConfig("SSS",   "🔷", 1_500,     0,  800),
    RankConfig("SR",    "🌟", 1_750,    0,  900),
    RankConfig("SSR",   "✨", 2_000,    0,  1_000),
    RankConfig("UR",    "💎", 2_500,    0, 1_250),
    RankConfig("LR",    "👑", 3_000,  0, 1_500),
    RankConfig("MP",    "🔱", 5_000,  0, 1_750),
    RankConfig("X",     "⚡", 6_000,  0, 2_000),
    RankConfig("XX",    "🌀", 7_500, 0, 2_250),
    RankConfig("XXX",   "🔥", 10_000, 0, 2_500),
    RankConfig("DX",    "💀", 12_000, 0, 2_750),
    RankConfig("ERROR", "❌", 15_000,0, 3_000),
]

RANKS_BY_ID: dict[str, RankConfig] = {r.rank: r for r in RANKS}

PHASE_RANKS: dict[str, list[str]] = {
    "gang":    ["F", "E", "D", "C"],
    "king":    ["C", "B", "A", "S", "SS"],
    "fist":    ["A", "S", "SS", "SSS", "SR", "SSR", "UR", "LR", "MP"],
    "emperor": ["MP", "X", "XX", "XXX", "DX", "ERROR"],
}

ATTACK_WIN_INFLUENCE_BONUS: dict[str, int] = {
    "gang":    15,
    "king":    50,
    "fist":    150,
    "emperor": 0,
}

STAR_BONUS_PERCENT: dict[int, int] = {
    0: 0,
    1: 10,
    2: 20,
    3: 30,
    4: 40,
    5: 50,
}