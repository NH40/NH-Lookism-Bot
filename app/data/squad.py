from dataclasses import dataclass


@dataclass
class RankConfig:
    rank: str
    emoji: str
    base_power: int
    min_influence: int
    recruit_cost: int


RANKS: list[RankConfig] = [
    RankConfig("F",     "⬛",  1,       0,       5),
    RankConfig("E",     "⬜",  5,       0,      10),
    RankConfig("D",     "🟦",  10,       0,     100),
    RankConfig("C",     "🟩", 25,      0,     250),
    RankConfig("B",     "🟨", 50,      0,   300),
    RankConfig("A",     "🟧", 75,     0,   500),
    RankConfig("S",     "🟥", 100,     0,   600),
    RankConfig("SS",    "💠", 120,     0,   750),
    RankConfig("SSS",   "🔷", 150,     0,  800),
    RankConfig("SR",    "🌟", 175,    0,  900),
    RankConfig("SSR",   "✨", 200,    0,  1_000),
    RankConfig("UR",    "💎", 250,    0, 1_250),
    RankConfig("LR",    "👑", 300,  0, 1_500),
    RankConfig("MP",    "🔱", 500,  0, 1_750),
    RankConfig("X",     "⚡", 600,  0, 2_000),
    RankConfig("XX",    "🌀", 750, 0, 2_250),
    RankConfig("XXX",   "🔥", 1_000, 0, 2_500),
    RankConfig("DX",    "💀", 1_200, 0, 2_750),
    RankConfig("ERROR", "❌", 1_500,0, 3_000),
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