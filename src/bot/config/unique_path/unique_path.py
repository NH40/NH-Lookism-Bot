"""Пути — 13 путей по 10 уровней, убеждение и квесты (конфиг). Формат уровней —
`config/development`.

Пользователь 2026-10-02 («одна из самых сложных механик»):
1. в зависимости от **потенциала и развития** приходит «подтверждение убеждений» — квест;
2. выполнил — **убеждение**, дальше копишь **фрагменты пути** (с босса **Ким Гапрена** на
   карте) и «Пробуждаешь путь» — путь **выпадает случайно** (2026-10-04: фрагменты нужны
   только для этого; второй квест «на путь» убран);
3. **10 уровней = 10 способностей**, уровни — за **очки пути**, которые даются за активность
   в боте (2026-10-04: «продумать так, чтобы путь качался только за 2 недели плотной игры»);
4. путь остаётся, пока не сброшен прогресс (патч, удаление банды, пробуждение); купившие
   несколько путей донатом переключают их в «Развитии».

Концепты путей — от пользователя (`docs/design/development_systems.md`, «Путь»), раскладка
способностей по уровням и числа — автор кода.
"""
from __future__ import annotations

from bot.config.development.development import scale_levels

from bot.constant.unique_path import PATH_SOURCE_DAILY
from bot.constant.dev_quest import (
    TASK_BOSS_WIN,
    TASK_BUILD,
    TASK_COLLECT,
    TASK_PERSONAL_TRAIN,
    TASK_RECRUIT,
    TASK_ROLL,
    TASK_SCHOOL_LESSON,
    TASK_TRAIN_EXTRAS,
    TASK_WAR_WIN,
    TASK_WIN_PVE,
    TASK_WIN_PVP,
)
from bot.constant.unique_path import (
    PATH_ABSORPTION,
    PATH_ADAPTATION,
    PATH_BUSINESS,
    PATH_COPY,
    PATH_DESPAIR,
    PATH_EVASION,
    PATH_FORESIGHT,
    PATH_INFINITE,
    PATH_OVERCOME,
    PATH_REFLECTION,
    PATH_SENSORY,
    PATH_SURE_HIT,
    PATH_TRAINING,
)
from bot.constant.characteristic import (
    POT_GANG_BOSS,
    POT_GEN_ZERO,
    POT_KING,
    POT_LEGEND,
    POT_MEMBER,
    POT_PEAK,
    POT_STRONG_KING,
    POT_WEAK_KING,
)


def _c(**kw) -> dict:
    return {"combat": kw}


def _e(**kw) -> dict:
    return {"eco": kw}


def _s(combat: dict | None = None, eco: dict | None = None, **special) -> dict:
    return {"combat": combat or {}, "eco": eco or {}, "special": special}


LEVELS: dict[str, tuple[dict, ...]] = {
    # Преодоление: путь слабого против сильного. Чем сильнее противник, тем сильнее ты: разрыв мощи
    # (2026-11-14, симуляция: без пробития урон слабого не проходил через прочность сильных билдов — пробитие по уровням)
    # закрывается по ходу боя, влияние усиливает армию, разница влияния — ещё раз. Шкала — за бои.
    PATH_OVERCOME: (
        _c(overcome=0.20, overcome_gap=0.10, overcome_gap_cap=0.75),
        _e(recruit_influence_cut=0.15, influence_bonus=0.05),
        _c(influence_power=0.03, durability=0.05, pierce=0.05),
        _c(overcome=0.20, loss_save=0.04),
        _c(influence_gap=0.05, overcome_gap=0.05, overcome_gap_cap=0.75),
        _e(recruit_cap=50, influence_rank_cut=0.10),
        _c(overcome=0.25, reduction=0.04, pierce=0.05),
        _c(influence_power=0.03, influence_gap=0.05),
        _c(overcome_gap=0.10, overcome_gap_cap=1.5, durability=0.05, pierce=0.05),
        _s({"overcome": 0.35, "attack": 0.05, "influence_power": 0.04, "pierce": 0.10}, {"recruit_cap": 100, "recruit_influence_cut": 0.15, "influence_bonus": 0.10}),
    ),
    # Отчаяние: противоположность Преодоления. Побеждать слабых и сохранять себя: бафы против более
    # слабой армии, при победе выживает больше своих, ресурсы защищены. Шкала — за победы и убитых.
    PATH_DESPAIR: (
        _c(despair=0.20, dominate=0.10),
        _c(win_loss_save=0.08),
        _c(despair=0.15, durability=0.05),
        _c(dominate=0.10, win_loss_save=0.06),
        _s({"loss_save": 0.05}, {"coin_protect": 0.25}),
        _c(despair=0.20, reduction=0.05, pierce=0.05),
        _c(dominate=0.15, attack=0.03),
        _s({"win_loss_save": 0.10}, {"coin_protect": 0.25}),
        _c(despair=0.20, dominate=0.10),
        _c(despair=0.30, dominate=0.20, win_loss_save=0.16, durability=0.15, attack=0.10, pierce=0.10),
    ),
    # Отражение: шкала копится прямо в бою. Дошла до доли своей мощи — выброс; выбили половину и три
    # четверти армии — отдельный ответ. Между боями не хранится.
    PATH_REFLECTION: (
        _c(reflect=0.04),
        _c(block=0.03, reflect_burst_at=0.40, reflect_burst_power=0.25),
        _c(reflect=0.04),
        _c(durability=0.05, reflect_loss_burst=0.03),
        _c(reflect=0.04, reflect_burst_power=0.25),
        _c(reduction=0.04, reflect_burst_at=0.35),
        _c(reflect=0.04, reflect_loss_burst=0.03),
        _c(counter=0.04, reflect_burst_power=0.25),
        _c(reflect=0.05, reflect_burst_at=0.30),
        _c(reflect=0.07, reflect_burst_power=0.50, reflect_loss_burst=0.07),
    ),
    # Поглощение: часть удара уходит в запас, запас возвращается врагу и растит атаку прямо в бою.
    # Шкала — за поглощённое, между боями хранится.
    PATH_ABSORPTION: (
        _c(absorb_store=0.04, absorb_return=0.20),
        _c(durability=0.04, absorb_power=0.05),
        _c(absorb_store=0.03, absorb_return=0.05),
        _c(block=0.03, absorb_power=0.05),
        _c(absorb_store=0.03),
        _c(absorb_return=0.05, absorb_power=0.08),
        _c(reduction=0.03, durability=0.04),
        _c(absorb_store=0.03, absorb_power=0.08),
        _c(absorb_return=0.05),
        _c(absorb_store=0.05, absorb_return=0.10, absorb_power=0.14),
    ),
    # Копирование: слияние способностей путей 5 последних противников. Шкала копирования — за бои с
    # другими игроками. Родословная Джинена усиливает и путь, и шкалу.
    PATH_COPY: (
        _s(memory_copy=0.15),
        _c(attack=0.03),
        _s(memory_copy=0.10),
        _c(dodge=0.02),
        _s(memory_copy=0.10),
        _c(durability=0.05),
        _s(memory_copy=0.10),
        _c(suppress=0.05),
        _s(memory_copy=0.10),
        _s(memory_copy=0.20),
    ),
    # Бесконечная техника: несколько уникальных техник сразу. Сколько — решает шкала копирования
    # (2, 3, 4, 5 техник, игрок выбирает сам), выбранные работают на 6–25%, остальные изученные — нет.
    PATH_INFINITE: (
        _s(infinite_techniques=True),
        _c(dodge=0.02),
        _c(attack=0.03),
        _s(infinite_power=0.02),
        _c(counter=0.03),
        _s(infinite_power=0.02),
        _c(dodge=0.02, attack=0.03),
        _s(infinite_power=0.02),
        _c(suppress=0.05),
        _s(infinite_power=0.03),
    ),
    # Предвидение: в бою уклонение, контратаки и побег, вне боя — разведка, шпионаж и безопасность.
    # Шкала открывает новые ступени разведки и прибавляет к боевым реакциям.
    PATH_FORESIGHT: (
        _s({"dodge": 0.03}, {"foresight": 1}),
        _c(counter=0.04, flee=0.02),
        _e(scout=1, security=1),
        _s({"dodge": 0.03}, {"foresight": 2}),
        _c(loss_save=0.05, counter=0.03),
        _e(spy_chance=0.05, spy_resist=0.05),
        _c(dodge=0.04, flee=0.02),
        _s({"counter": 0.04}, {"foresight": 3, "logs": 1}),
        _e(scout=2, security=1),
        _s({"dodge": 0.05, "suppress": 0.10, "counter": 0.06, "attack": 0.10}, {"spy_chance": 0.10, "spy_resist": 0.10, "logs": 2}),
    ),
    # Сенсорика (менеджер Ким): война вне сражения. Метки, слежка, снятие чужой безопасности, личные
    # саботажи. В самом бою почти не помогает.
    PATH_SENSORY: (
        _e(marks=1, sabotage_chance=0.05),
        _e(logs=1, security_pierce=1),
        _e(marks=1, sabotage_cooldown=0.15),
        _s(sabotage_marked=True),
        _e(scout=1, spy_chance=0.05),
        _e(marks=1, sabotage_loot=0.20),
        _s(neutralize_security=True),
        _e(logs=2, security_pierce=1, sabotage_chance=0.05),
        _e(marks=2, sabotage_cooldown=0.15),
        _e(scout=3, logs=3, sabotage_loot=0.30, security_pierce=2, spy_chance=0.10),
    ),
    # Гарантированный удар: самый военный путь. Урон проходит сквозь уклонение и броню, атака растёт,
    # оборона держит. Шкала войны — за победы и убитых.
    PATH_SURE_HIT: (
        _c(sure_hit=0.10, attack=0.04),
        _c(crit_chance=0.04, pierce=0.05),
        _c(sure_hit=0.08, durability=0.05, cqc_accel=0.5),
        _c(pierce=0.08, attack=0.05),
        _c(sure_hit=0.10, block=0.03),
        _c(attack=0.07, crit_power=0.25, cqc_boost=0.10),
        _c(sure_hit=0.10, reduction=0.05),
        _c(pierce=0.10, attack=0.07),
        _c(sure_hit=0.12, crit_chance=0.06),
        _c(sure_hit=0.15, no_dodge=True, attack=0.12, pierce=0.12, cqc_boost=0.15, cqc_accel=0.5),
    ),
    # Адаптация (путь Александровых): чем дольше бой, тем сильнее. Шкала хранится между боями и даёт
    # бафы и статистам, и уникам. С родословной Александровых шкала растёт быстрее и бьёт сильнее.
    PATH_ADAPTATION: (
        _c(adapt_threshold=0.30, adapt_bonus=0.20, endure_attack=0.02),
        _c(adapt_guard=0.05, endure_guard=0.01),
        _c(adapt_bonus=0.15, endure_unique=0.03),
        _c(durability=0.08, endure_attack=0.02),
        _c(adapt_bonus=0.20, endure_guard=0.01),
        _c(adapt_guard=0.05, durability=0.07),
        _c(adapt_threshold=0.25, endure_attack=0.03),
        _c(adapt_bonus=0.20, endure_unique=0.04),
        _c(adapt_guard=0.05, endure_guard=0.02),
        _c(adapt_bonus=0.35, endure_attack=0.05, endure_unique=0.05, durability=0.10),
    ),
    # Бесконечная тренировка: всё про тренировки, своя шкала — КПД. Лучше всего с родословными Самдака
    # и Ямадзаки.
    PATH_TRAINING: (
        _e(extras_training=3, dev_points=0.05),
        _e(extras_extra_roll=0.10, extras_coverage=3),
        _e(extras_training_cooldown=0.10, personal_cooldown=0.05),
        _e(extras_training=3, dev_points=0.05),
        _e(extras_extra_roll=0.10, extras_coverage=3),
        _e(dev_points=0.15, personal_cooldown=0.05),
        _e(extras_training_cooldown=0.10, extras_coverage=4),
        _e(extras_extra_roll=0.15, dev_points=0.10),
        _e(extras_training=4, personal_cooldown=0.10),
        _e(extras_extra_roll=0.25, extras_training=5, extras_coverage=5, dev_points=0.20),
    ),
    # Уклонение: уклонение выше обычного потолка и работает там, где от удара «не увернуться»;
    # уклонившиеся бьют в ответ, армия разгоняется от каждого уклонения. Шкала — за уклонения.
    PATH_EVASION: (
        _c(dodge=0.05, dodge_counter=0.08),
        _c(flee=0.02, dodge_surge=0.10),
        _c(dodge=0.05, dodge_cap=0.03),
        _c(counter=0.03, dodge_true=0.25),
        _c(dodge=0.05, dodge_counter=0.08),
        _c(reduction=0.03, dodge_surge=0.15),
        _c(dodge=0.05, dodge_cap=0.05),
        _c(dodge=0.05, dodge_true=0.25),
        _c(loss_save=0.05, dodge_counter=0.10),
        _c(dodge=0.06, counter=0.03, dodge_cap=0.05, dodge_surge=0.15, dodge_true=0.25, dodge_counter=0.10),
    ),
    # Бизнесмена: огромный доход, пассивные деньги и фрагменты. Шкала — от заработанных денег.
    PATH_BUSINESS: (
        _e(income=0.10, passive_income=300),
        _e(storage_hours=4, fragment_bonus=0.10),
        _e(upgrade_discount=0.10, passive_income=300),
        _e(income=0.10, tax_relief=0.05),
        _e(build_discount=0.10, fragment_bonus=0.15),
        _e(tax_relief=0.10, passive_income=500),
        _e(income=0.12, storage_hours=4),
        _e(storage_hours=8, fragment_bonus=0.15),
        _e(upgrade_discount=0.10, build_discount=0.10, passive_income=900),
        _e(income=0.20, fragment_bonus=0.20, passive_income=1500),
    ),
}

# Множители баланса — подобраны симуляцией 2026-11-14 (30 билдов уровня Никиты, турнир на настоящем движке боя,
# ~1.5 млн боёв). Умножают боевые числа уровней при загрузке (`config/development.scale_levels`): тексты и бой видят
# одно и то же. Пользователь: слабое — сильнее, перекачанное — слабее, экономические специализации не трогать.
PATH_BALANCE: dict[str, float] = {
    PATH_OVERCOME: 1.25,
    PATH_DESPAIR: 1.8,
    PATH_REFLECTION: 1.2,
    PATH_ABSORPTION: 0.85,
    PATH_COPY: 0.8,
    PATH_INFINITE: 0.8,
    PATH_FORESIGHT: 1.1,
    PATH_ADAPTATION: 1.15,
}
LEVELS = scale_levels(LEVELS, PATH_BALANCE)


# «Подтверждение убеждений» приходит, когда сумма рангов четырёх характеристик (индексы в
# RANK_LADDER) достигает порога — у кого потенциал выше, тому раньше (пользователь: «в
# зависимости от потенциала и развития игрока»).
CONVICTION_RANK_SUM: dict[str, int] = {
    POT_MEMBER: 88,
    POT_GANG_BOSS: 80,
    POT_WEAK_KING: 72,
    POT_KING: 64,
    POT_STRONG_KING: 56,
    POT_GEN_ZERO: 48,
    POT_PEAK: 40,
    POT_LEGEND: 32,
}
CONVICTION_QUEST: dict[str, int] = {TASK_WIN_PVE: 10, TASK_PERSONAL_TRAIN: 5, TASK_BOSS_WIN: 1}
# «Пробудить путь»: столько фрагментов пути (с Ким Гапрена) после квеста убеждения.
PATH_AWAKEN_FRAGMENTS = 100

# Уровни пути — за очки пути. 2-й — 240, 10-й — 1 200; до 10-го — 6 480 очков.
PATH_LEVEL_COST_PER_LEVEL = 120

# Очки пути за активность (начисляются, только пока путь пробуждён). Источник → (очки,
# минимальный интервал между засчитанными событиями, сек). Защита от абуза — интервал на
# КАЖДЫЙ источник: частое повторение одного действия (PvP с твинком, сбор дохода раз в
# минуту, крутка пачкой) засчитывается не чаще интервала, а сами действия и так ограничены
# своими КД/ресурсами. Темп (решение автора кода, пользователь — «2 недели плотной игры»):
# плотная игра ≈ 450 очков в день → 10-й уровень за ~14 дней; теоретический максимум (16 ч
# в сутки, каждое действие по интервалу, император с войнами) ≈ 690 в день — не быстрее ~9
# дней.
PATH_POINT_SOURCES: dict[str, tuple[int, int]] = {
    TASK_PERSONAL_TRAIN: (6, 55 * 60),
    TASK_TRAIN_EXTRAS: (3, 55 * 60),
    TASK_SCHOOL_LESSON: (4, 55 * 60),
    TASK_WIN_PVE: (4, 30 * 60),
    TASK_WIN_PVP: (8, 60 * 60),
    TASK_BOSS_WIN: (12, 60 * 60),
    TASK_WAR_WIN: (20, 6 * 60 * 60),
    TASK_COLLECT: (2, 2 * 60 * 60),
    TASK_BUILD: (3, 60 * 60),
    TASK_RECRUIT: (2, 60 * 60),
    TASK_ROLL: (1, 30 * 60),
    PATH_SOURCE_DAILY: (10, 20 * 60 * 60),
}


def path_level_cost(next_level: int) -> int:
    return PATH_LEVEL_COST_PER_LEVEL * next_level


# Путь тренировок (пользователь 2026-10-16): КПД всех тренировок растёт от дней на пути и от
# каждой тренировки, потолок — по уровню пути. КПД: больше очков развития и шансов, короче КД,
# дешевле тренировка техник, быстрее очки пути.
TRAINING_KPD_PER_DAY = 0.02
TRAINING_KPD_PER_REP = 0.005
TRAINING_KPD_CAP_PER_LEVEL = 0.06  # 10-й уровень — до +60%
TRAINING_KPD_EXTRAS_PP = 20  # КПД 1.0 = +20 п.п. к шансам тренировки статистов и занятий школ

# Путь Бесконечной техники (пользователь 2026-11-04): сколько техник активно одновременно решает
# шкала копирования. Выбранные работают с этой силой (активная — 100%), уровни пути её поднимают.
# Симуляция 2026-11-14 (30 билдов уровня Никиты): при 70% у выбранных и 20% у остальных изученных путь стоил ×80 армии —
# множители техник перемножаются. Теперь 6% + уровни (до 15%) + шкала (до 10%) = 25% на 10-м уровне, остальные не работают.
INFINITE_EXTRA_TECHNIQUE_POWER = 0.06
INFINITE_MIN_TECHNIQUES = 2
INFINITE_MAX_TECHNIQUES = 5
INFINITE_GAUGE_PER_TECHNIQUE = 33  # каждые 33 шкалы — ещё одна техника

PATH_SWAP_COOLDOWN_SECONDS = 15 * 60
# Предвидение: сколько симуляций для прогноза по уровням (точность растёт с уровнем).
FORESIGHT_SIMULATIONS: dict[int, int] = {1: 8, 2: 16, 3: 40}
