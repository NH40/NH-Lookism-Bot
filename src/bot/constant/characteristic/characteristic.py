"""Лестница рангов F-..Infinity (raw-notes «Профиль») — общая для характеристик игрока
(Сила/Скорость/Выносливость/Ловкость) и рангов статистов (`extra`, см. raw-notes
«Карта»: «получает от F до EX/EXR/ZZZ ранга статистов»).

Подтверждено пользователем 2026-09-21 (AskUserQuestion): статисты шагают по ПОЛНОЙ
лестнице с минус/плюс на первых буквах (F-, F, F+, E-, E, E+, ...), а не по упрощённой
"одна ступень на букву" — несмотря на то что пример мощи в raw-notes был дан только по
целым буквам (F=10, E=20, D=40, C=70, B=110), это сокращение автора заметок для первых
ПЯТИ ПОДРЯД ИДУЩИХ ступеней (F-, F, F+, E-, E), не имена конкретных рангов и не
отдельная упрощённая лестница (см. `config/characteristic.extra_power_for_rank`).

Ранг сравнивается по имени (`==`) и по позиции в лестнице (следующий/предыдущий ранг) —
именованные константы, не строковые литералы (см. CLAUDE.md, правило про `constant/`).
"""
from __future__ import annotations

RANK_LADDER: tuple[str, ...] = (
    "F-", "F", "F+",
    "E-", "E", "E+",
    "D-", "D", "D+",
    "C-", "C", "C+",
    "B-", "B", "B+",
    "A-", "A", "A+",
    "S-", "S", "S+",
    "SS", "SSS", "SR", "SSR", "UR", "LR", "MR",
    "X", "XX", "XXX",
    "EX", "DX", "CX", "BX", "AX", "SX", "UX", "LX", "MX",
    "EXR", "DXR", "CXR", "BXR", "AXR", "SXR",
    "Y", "YY", "YYY",
    "Z", "ZZ", "ZZZ",
    "Infinity",
)

RANK_INDEX: dict[str, int] = {rank: i for i, rank in enumerate(RANK_LADDER)}

RANK_STARTING = RANK_LADDER[0]  # "F-" — стартовый ранг любой характеристики/статиста.
RANK_MAX = RANK_LADDER[-1]  # "Infinity" — теоретический потолок лестницы.

# --- Характеристики игрока (raw-notes «Профиль») ---
# Хранятся в `users` индексом ранга в RANK_LADDER (0 = F-). Код используется в callback'ах
# и как ключ колонки — константа, не литерал.
STAT_STRENGTH = "strength"
STAT_SPEED = "speed"
STAT_ENDURANCE = "endurance"
STAT_AGILITY = "agility"
STATS: tuple[str, ...] = (STAT_STRENGTH, STAT_SPEED, STAT_ENDURANCE, STAT_AGILITY)

# --- Потенциал: 8 стадий (пользователь, 2026-09-30) ---
# Выдаётся случайно при регистрации, прокачать нельзя; новый случайный — только при
# перерождении кулака (механика позже). От стадии — очки личной тренировки.
POT_MEMBER = "member"
POT_GANG_BOSS = "gang_boss"
POT_WEAK_KING = "weak_king"
POT_KING = "king"
POT_STRONG_KING = "strong_king"
POT_GEN_ZERO = "gen_zero"
POT_PEAK = "peak"
POT_LEGEND = "legend"
POTENTIAL_ORDER: tuple[str, ...] = (
    POT_MEMBER,
    POT_GANG_BOSS,
    POT_WEAK_KING,
    POT_KING,
    POT_STRONG_KING,
    POT_GEN_ZERO,
    POT_PEAK,
    POT_LEGEND,
)

CB_STATS_OPEN = "stats:open"
CB_STATS_UP_PREFIX = "stats:up:"
"""f"{CB_STATS_UP_PREFIX}{stat}:{STATS_UP_ONE|STATS_UP_FIVE|STATS_UP_MAX}"."""
STATS_UP_ONE = "1"
STATS_UP_FIVE = "5"
STATS_UP_MAX = "max"

# --- Мастерство (raw-notes «Профиль»): 4 ветки по 3 ступени ---
MASTERY_STRENGTH = "strength"
MASTERY_SPEED = "speed"
MASTERY_ENDURANCE = "endurance"
MASTERY_TECHNIQUE = "technique"
MASTERIES: tuple[str, ...] = (MASTERY_STRENGTH, MASTERY_SPEED, MASTERY_ENDURANCE, MASTERY_TECHNIQUE)
