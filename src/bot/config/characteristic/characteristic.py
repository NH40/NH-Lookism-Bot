"""Формулы, связанные с лестницей рангов (`constant/characteristic.RANK_LADDER`) — не
магические числа в хендлерах/сервисах (см. CLAUDE.md, правило 8).

Подтверждено пользователем 2026-09-21 (AskUserQuestion, второй вопрос той же серии):
формула мощи статиста, выведенная из 5 примеров raw-notes (F=10, E=20, D=40, C=70,
B=110 — прирост между соседними ступенями растёт на +10 с каждым шагом: +10, +20, +30,
+40), продолжается ДО САМОГО ВЕРХА лестницы, не выравнивается/не меняется на каком-то
этапе. `n` — 0-based индекс ранга в `RANK_LADDER` (F-=0, F=1, F+=2, ..., Infinity=52).

Формула: mощь(n) = 10 × (1 + n×(n+1)/2) — треугольное число, идеально воспроизводит
все 5 исходных примеров raw-notes (F=10, E=20, D=40, C=70, B=110), если считать их
ПЯТЬЮ ПОДРЯД ИДУЩИМИ ступенями полной лестницы — n=0..4, то есть F-, F, F+, E-, E
(не буквально ранги "F"/"E"/"D"/"C"/"B" по отдельности — сами буквы в примере были
сокращением автора заметок, не именами конкретных ступеней; см. AskUserQuestion
2026-09-21, где эта формула была выведена и подтверждена именно в таком виде). На
верхних рангах даёт уже десятки тысяч мощи (Infinity, n=52: 13790) — ожидаемо для
эндгейм-контента фазы Кулака.
"""
from __future__ import annotations

from bot.config.game import EXTRA_TRAINING_STAGE1_POWER_MULTIPLIER, EXTRA_TRAINING_STAGE2_POWER_BONUS_PERCENT
from bot.constant.characteristic import RANK_INDEX

# --- Мощь статиста по рангу (raw-notes «Карта») ---

EXTRA_RANK_POWER_BASE = 10


def extra_power_for_rank(rank: str) -> int:
    n = RANK_INDEX[rank]
    return EXTRA_RANK_POWER_BASE * (1 + n * (n + 1) // 2)


def extra_unit_power(rank: str, stars: int, training_level: int) -> int:
    """Мощь ОДНОЙ единицы статиста в стопке (см. `db/models/extra.py` — статисты
    хранятся стопками, мощь никогда не хранится поштучно, всегда считается по этой
    формуле). `training_level` — сколько раз статист прошёл этап 1 тренировки (мощь
    ×1.2 каждый раз, накопительно), `stars` — сколько раз прошёл этап 2 (+50% каждая
    звезда) — оба множителя берутся из `config/game` (см. `services/training`), чтобы
    не дублировать числа в двух местах."""
    base = extra_power_for_rank(rank)
    power = base * (EXTRA_TRAINING_STAGE1_POWER_MULTIPLIER**training_level)
    power *= (1 + EXTRA_TRAINING_STAGE2_POWER_BONUS_PERCENT / 100) ** stars
    return round(power)


# --- Характеристика "Сила" игрока (raw-notes «Профиль») ---
# «каждый повышения ранга силы даёт по +1% к мощи» — процентных пунктов ровно столько,
# сколько ступеней пройдено от старта (F-, 0%).

STRENGTH_POWER_PERCENT_PER_RANK = 1


def strength_power_percent(rank: str) -> int:
    return RANK_INDEX[rank] * STRENGTH_POWER_PERCENT_PER_RANK


# --- Мастерство (raw-notes «Профиль»: Стена -> Трансцендентность -> Мастерство, 0-3) ---
# Значения — ИТОГОВЫЙ бонус на ступени (не накопительная сумма ступеней) — так прочитан
# формат raw-notes "10%/25%/50%"/"−10/20/30%" (список величин ПО ступеням, а не
# прирост между ними, в отличие от формулы мощи статиста выше, где явно был дан именно
# прирост). Не переспрашивалось отдельным вопросом (см. CLAUDE.md, "Открытые вопросы
# дизайна" — если чтение окажется неверным, поправить здесь одной строкой, потребителей
# формулы на момент написания ещё нет).

MASTERY_MIN_TIER = 0
MASTERY_MAX_TIER = 3

_STRENGTH_MASTERY_POWER_PERCENT: dict[int, int] = {0: 0, 1: 10, 2: 25, 3: 50}
_SPEED_MASTERY_CD_REDUCTION_PERCENT: dict[int, int] = {0: 0, 1: 10, 2: 20, 3: 30}


def strength_mastery_power_percent(tier: int) -> int:
    return _STRENGTH_MASTERY_POWER_PERCENT[tier]


def speed_mastery_cd_reduction_percent(tier: int) -> int:
    return _SPEED_MASTERY_CD_REDUCTION_PERCENT[tier]


# Мастерство Выносливости/Техники (важны "в сражениях") — формулы не даны в raw-notes и
# не реализованы: конкретные проценты уклонения/блока/контратаки/побега — открытый
# вопрос дизайна (см. CLAUDE.md), уточнить перед реализацией домена `combat`.
