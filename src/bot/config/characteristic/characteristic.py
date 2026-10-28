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

from typing import NamedTuple

from bot.config.game import EXTRA_TRAINING_STAGE1_POWER_MULTIPLIER, EXTRA_TRAINING_STAGE2_POWER_BONUS_PERCENT
from bot.constant.characteristic import (
    POT_GANG_BOSS,
    POT_GEN_ZERO,
    POT_KING,
    POT_LEGEND,
    POT_MEMBER,
    POT_PEAK,
    POT_STRONG_KING,
    POT_WEAK_KING,
    RANK_INDEX,
)

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


# --- Прокачка характеристик за очки развития (пользователь, 2026-09-30) ---
# «F→F+ за одно очко и каждые два ранга повышать цену на одно очко» — вдвое дешевле
# первого варианта (1 400 очков до Infinity на характеристику): шаг с ранга n на n+1 стоит
# 1 + n // 2 очков → F-→F и F→F+ по 1, F+→E- и E-→E по 2, … Итого 702 очка на одну
# характеристику до Infinity, 2 808 на все четыре.

STAT_MAX_INDEX = 52  # Infinity — последний индекс RANK_LADDER


def stat_rank_up_cost(index: int, discount: float = 0.0) -> int:
    """Цена шага с ранга `index` на `index + 1`. `discount` — скидка систем развития
    (Самдак, гений тренировок; уже обрезанная потолком), не меньше 1 очка."""
    base = 1 + index // 2
    return max(1, round(base * (1 - discount))) if discount else base


def stat_ranks_affordable(index: int, points: int, limit: int | None = None, discount: float = 0.0) -> tuple[int, int]:
    """Сколько рангов подряд можно купить от `index` на `points` (не больше `limit` и не выше
    Infinity) → (рангов, цена). Шагов максимум 52 — цикл дешёвый."""
    ranks = cost = 0
    while index + ranks < STAT_MAX_INDEX and (limit is None or ranks < limit):
        step = stat_rank_up_cost(index + ranks, discount)
        if cost + step > points:
            break
        cost += step
        ranks += 1
    return ranks, cost


# --- Потенциал → личная тренировка (пользователь, 2026-09-30: «от потенциала зависит,
# сколько в личной тренировке будет получено очков»; raw-notes: «есть шанс в зависимости от
# потенциала, что игрок не получит ничего»). Числа — предложение автора кода, калибровка:
# при ~12 тренировках в сутки (КД 1 час) все 4 характеристики до Infinity (2 808 очков)
# у Легенды ≈ месяц, у Короля ≈ 3 месяца, у Члена банды ≈ 7 месяцев.

class PotentialTraining(NamedTuple):
    min_points: int
    max_points: int
    nothing_percent: int  # шанс не получить ничего


POTENTIAL_TRAINING: dict[str, PotentialTraining] = {
    POT_MEMBER: PotentialTraining(1, 2, 30),
    POT_GANG_BOSS: PotentialTraining(1, 3, 25),
    POT_WEAK_KING: PotentialTraining(2, 3, 20),
    POT_KING: PotentialTraining(2, 4, 15),
    POT_STRONG_KING: PotentialTraining(3, 5, 12),
    POT_GEN_ZERO: PotentialTraining(4, 6, 10),
    POT_PEAK: PotentialTraining(5, 8, 7),
    POT_LEGEND: PotentialTraining(6, 10, 5),
}

# Шанс выпадения стадии при регистрации, % (сумма 100) — чем выше, тем реже.
POTENTIAL_START_PERCENT: dict[str, float] = {
    POT_MEMBER: 30,
    POT_GANG_BOSS: 22,
    POT_WEAK_KING: 17,
    POT_KING: 13,
    POT_STRONG_KING: 9,
    POT_GEN_ZERO: 5,
    POT_PEAK: 3,
    POT_LEGEND: 1,
}


# --- Мастерство выносливости и техники (raw-notes «Сражения») ---
# «Мастерство выносливости позволяет сохранять 10/20/30% статистов, которые проиграли»;
# «порог техники увеличивает шансы характеристики на множитель 1/5/10 в зависимости от
# количества мастерства техники» — ступени 1/2/3 → ×1/×5/×10, без мастерства — ×1.
_ENDURANCE_MASTERY_LOSS_SAVE_PERCENT: dict[int, int] = {0: 0, 1: 10, 2: 20, 3: 30}
_TECHNIQUE_MASTERY_MULTIPLIER: dict[int, int] = {0: 1, 1: 1, 2: 5, 3: 10}


def endurance_mastery_loss_save_percent(tier: int) -> int:
    return _ENDURANCE_MASTERY_LOSS_SAVE_PERCENT[tier]


def technique_mastery_multiplier(tier: int) -> int:
    return _TECHNIQUE_MASTERY_MULTIPLIER[tier]


# --- Характеристики в бою (пользователь 2026-09-30: «считай самостоятельно, чтобы подходило
# по балансу»; Выносливость — «поглощает часть урона и даёт множитель к блокам отряда»).
# Калибровка: без мастерства техники даже Infinity даёт скромные +2.6 п.п. (базовые шансы
# 5%); с мастерством техники ×10 — до ~31% на реакцию. Потолки ниже не дают армиям двух
# прокачанных игроков стать почти бессмертными.
AGILITY_DODGE_PP_PER_RANK = 0.05  # +п.п. уклонения за ранг Ловкости
SPEED_FLEE_PP_PER_RANK = 0.05  # +п.п. побега за ранг Скорости
ENDURANCE_BLOCK_MULT_PERCENT_PER_RANK = 1  # блок × (1 + 1% за ранг Выносливости)
ENDURANCE_ABSORB_PERCENT_PER_RANK = 0.2  # доля поглощённого урона, % за ранг (Infinity 10.4%)
# raw-notes: «Ловкость — две атаки сразу, игнорируя КД, шанс второй атаки +1% за уровень»;
# «Скорость — −1% времени у противника на принятие сражения с каждым рангом».
AGILITY_FREE_ATTACK_PERCENT_PER_RANK = 1
SPEED_ACCEPT_WINDOW_PERCENT_PER_RANK = 1
REACTION_MAX = 0.40  # потолок одной реакции (уклонение/блок/контратака/побег)
REACTIONS_TOTAL_MAX = 0.80  # потолок суммы всех реакций


def statist_unit_power(rank: str, stars: int, training_level: int, school: str = "", school_level: int = 0) -> float:
    """Мощь статиста с учётом школы учителя: школа Силы (и немного Скорости) прибавляет к
    мощи бойца за каждый уровень (`config/school`). Без школы — ровно `extra_unit_power`."""
    power = extra_unit_power(rank, stars, training_level)
    if school and school_level:
        from bot.config.school import SCHOOL_POWER_PER_LEVEL

        power *= 1 + SCHOOL_POWER_PER_LEVEL.get(school, 0.0) * school_level
    return power



# Очки потенциала (пользователь 2026-10-28): «как очки пути — за время игры копятся, накопив,
# можно повысить потенциал; за месяц плотной игры — на ~4 ранга, до Легенды — сложно».
# Источники и интервалы — те же, что у очков пути (≈450 очков в день плотной игры), но без
# условия «путь пробуждён». Цена — с какого потенциала на следующий; растёт ступенями:
# первые 4 перехода ≈ 3+5+8+14 = 30 дней, до Легенды всего ≈ 155 дней.
POTENTIAL_UPGRADE_COST: dict[str, int] = {
    POT_MEMBER: 1_350,
    POT_GANG_BOSS: 2_250,
    POT_WEAK_KING: 3_600,
    POT_KING: 6_300,
    POT_STRONG_KING: 11_250,
    POT_GEN_ZERO: 18_000,
    POT_PEAK: 27_000,
}
