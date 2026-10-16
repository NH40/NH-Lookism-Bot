"""PvP-покер (конфиг). Перенос из 1.0 (`app/constants/poker.py`); бай-ин — под экономику 2.0
(решение автора кода), остальное — как в 1.0."""
from __future__ import annotations

POKER_MIN_PLAYERS = 2
POKER_MAX_PLAYERS = 6
POKER_BUY_INS: tuple[int, ...] = (2_000, 10_000, 50_000, 250_000, 1_000_000, 2_000_000)  # кнопки при создании
POKER_WAIT_OPTIONS_SECONDS: tuple[int, ...] = (60, 180, 300)
# Блайнды от бай-ина (~20 больших блайндов в стеке).
POKER_BIG_BLIND_RATIO = 20
POKER_SMALL_BLIND_RATIO = 40
# Невидимый рейк с банка — уходит из экономики (как в 1.0).
POKER_RAKE_PERCENT = 0.05
# На ход — столько секунд, потом авто-чек или авто-фолд.
POKER_ACTION_TIMEOUT_SECONDS = 30
POKER_TICK_SECONDS = 3
POKER_LOBBY_LIMIT = 10
