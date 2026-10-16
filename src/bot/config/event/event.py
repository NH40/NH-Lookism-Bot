"""События на карте — частота, длительность, сила боссов и награды (конфиг).

raw-notes: «4 типа события, которые появляются на карте… время подбери сам, учти, что они
должны быть довольно частыми и рандомными». Числа — решение автора кода; калибровка —
многомесячный гринд (пользователь в переписке с Никитой: «из недельного гринда в
многомесячный»): путь до 10 уровня — порядка 150 побед над Ким Гапреном.
"""
from __future__ import annotations

from bot.constant.event import BOSS_ELITE, BOSS_GAPRYONG, BOSS_JINYEONG
from bot.constant.phase import PHASE_CIRCLE, PHASE_FIST, PHASE_GANG

EVENT_TICK_SECONDS = 300  # фоновый проход: появление событий
# Шанс появления босса каждого вида за проход, если он сейчас не на карте: в среднем раз в
# ~5 часов, но случайно (raw-notes: «частыми и рандомными»).
BOSS_SPAWN_CHANCE_PER_TICK = EVENT_TICK_SECONDS / (5 * 60 * 60)
BOSS_DURATION_SECONDS = 60 * 60
TEACHER_SPAWN_CHANCE_PER_TICK = EVENT_TICK_SECONDS / (4 * 60 * 60)
TEACHER_DURATION_SECONDS = 2 * 60 * 60
TEACHERS_MAX_ACTIVE = 2
# Пуш о новом событии — только тем, кто заходил в игру за последние N дней, пачками.
EVENT_PUSH_ACTIVE_DAYS = 3
EVENT_PUSH_BATCH = 25
EVENT_PUSH_PAUSE_SECONDS = 1.0

# Сила босса — % мощи лагеря атаки игрока (как Том Ли в мастерстве), со своими способностями
# (описания боссов в raw-notes «Рейды»).
# Калибровка симуляцией (2026-10-02): армия «под босса» (сильные бойцы против Гапрена и
# Джинена) выигрывает в большинстве боёв, толпа слабых — редко; бафы систем развития сдвигают.
BOSS_POWER_PERCENT: dict[str, int] = {BOSS_GAPRYONG: 85, BOSS_JINYEONG: 85, BOSS_ELITE: 90}
BOSS_POWER_MIN = 1_000
# Единица босса — как самый сильный боец игрока, но не слабее порога фазы (ранг): «слабые»
# для Джинена и «корм» для Гапрена — те, кто заметно ниже неё.
BOSS_UNIT_FLOOR_RANK: dict[str, str] = {PHASE_GANG: "C", PHASE_CIRCLE: "S", PHASE_FIST: "EX"}
BOSS_MODS: dict[str, dict] = {
    # Гапрен: после победы над каждым статистом немного растёт — против него сильные бойцы.
    BOSS_GAPRYONG: {"grow_on_kill": 0.25, "durability": 0.15},
    # Джинен: лечится, когда его бьют слабые — только сильные статисты.
    BOSS_JINYEONG: {"heal_vs_weak": 0.45},
    # Элита: от его атак не увернуться — ловкость бесполезна; сам ловкий.
    BOSS_ELITE: {"no_dodge": True, "dodge": 0.15},
}

# Награда за победу: фрагменты своего вида — (мин, макс) по фазе игрока.
BOSS_FRAGMENTS: dict[str, tuple[int, int]] = {
    PHASE_GANG: (5, 8),
    PHASE_CIRCLE: (7, 11),
    PHASE_FIST: (9, 14),
}
