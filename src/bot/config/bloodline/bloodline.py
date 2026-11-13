"""Родословные — 10 веток по 10 уровней (конфиг). Формат уровней — `config/development`.

Пользователь 2026-10-02: родословная выбирается один раз навсегда (смена — донатом),
пробуждается каплями крови «на протяжении многих патчей»; «каждый уровень — чуть ли не
новая механика». Направления веток — от пользователя (`docs/design/development_systems.md`,
«Направления 10 родословных»), раскладка по уровням и числа — автор кода.

Уровень 1 даётся сразу при выборе (иначе выбор родословной ничего бы не значил до первых
капель), уровни 2–10 — за капли крови (`bloodline_level_cost`).
"""
from __future__ import annotations

from bot.config.development.development import scale_levels

from bot.constant.bloodline import (
    BLOODLINE_ELITE,
    BLOODLINE_GAPRYONG,
    BLOODLINE_HANSU,
    BLOODLINE_PENGUAN,
    BLOODLINE_JINCHEOL,
    BLOODLINE_JINYEONG,
    BLOODLINE_KURODA,
    BLOODLINE_MUJIN,
    BLOODLINE_SAMDAK,
    BLOODLINE_SOPHIA,
    BLOODLINE_YAMAZAKI,
)
from bot.constant.build import SOURCE_BLOODLINE, SOURCE_PATH, SOURCE_TECHNIQUE
from bot.constant.characteristic import RANK_INDEX


def _c(**kw) -> dict:
    return {"combat": kw}


def _e(**kw) -> dict:
    return {"eco": kw}


def _s(combat: dict | None = None, eco: dict | None = None, **special) -> dict:
    return {"combat": combat or {}, "eco": eco or {}, "special": special}


LEVELS: dict[str, tuple[dict, ...]] = {
    # Элита: бизнес. Потолок прокачки бизнеса выше обычного (до 15), доход, хранилище, налог меньше.
    # В боях забирает часть NHCoin проигравшего.
    BLOODLINE_ELITE: (
        _e(income=0.10),
        _e(business_cap=1),
        _e(storage_hours=6, upgrade_discount=0.10),
        _e(business_cap=1, tax_relief=0.15),
        _e(battle_loot=0.03),
        _e(business_cap=1, income=0.10),
        _e(tax_relief=0.15, build_discount=0.15),
        _e(business_cap=1, battle_loot=0.03),
        _e(income=0.15, gacha_luck=0.03),
        _e(business_cap=1, income=0.15, battle_loot=0.04, tax_relief=0.10),
    ),
    # Муджина: огромнейшая сила и удар до боя: часть армии бьёт прежде, чем начнётся сражение.
    BLOODLINE_MUJIN: (
        _e(army_power=0.05),
        _c(crit_power=0.20),
        _c(pre_strike_share=0.10, pre_strike_power=0.30),
        _s({"pierce": 0.05, "seirim_boost": 0.10}, {"army_power": 0.05}),
        _c(opening=0.20),
        _s({"pre_strike_share": 0.10, "pre_strike_power": 0.15}, {"army_power": 0.07}),
        _c(durability=0.08),
        _c(crit_chance=0.05, pre_strike_share=0.10, seirim_boost=0.10),
        _e(army_power=0.08),
        _s({"pierce": 0.10, "pre_strike_share": 0.10, "pre_strike_power": 0.30, "seirim_boost": 0.15}, {"army_power": 0.12}),
    ),
    # Джинена: копирование (пути Копирования и Бесконечной техники, источники противника в бою) и гений
    # медицины: уровни дешевле, сила выше, зелья с дополнительным эффектом.
    BLOODLINE_JINYEONG: (
        _s({"attack": 0.02, "durability": 0.02}, {"medicine_discount": 0.25, "potion_discount": 0.10}),
        _s(copy_path_boost=0.20, copy_gauge_speed=0.25),
        _s(copy_sources=(SOURCE_TECHNIQUE,), copy_strength=0.25),
        _s({"attack": 0.03, "durability": 0.03}, {"potion_power": 0.15, "potion_duration": 0.15}, medicine_power=0.15),
        _s(None, {"medicine_discount": 0.25, "teacher_quest_cut": 1}),
        _s(copy_sources=(SOURCE_TECHNIQUE, SOURCE_BLOODLINE), copy_strength=0.10),
        _s(None, {"potion_heal": 0.02}, copy_path_boost=0.25),
        _s(None, {"potion_power": 0.20, "potion_auto": 1}, medicine_power=0.15, copy_gauge_speed=0.25),
        _s(None, {"teacher_quest_cut": 1}, copy_sources=(SOURCE_TECHNIQUE, SOURCE_BLOODLINE, SOURCE_PATH), copy_strength=0.10),
        _s(None, {"potion_heal": 0.03, "potion_duration": 0.25}, copy_strength=0.15, copy_path_boost=0.30, medicine_power=0.25, copy_gauge_speed=0.50),
    ),
    # Ким Гапрена: огромные характеристики со старта, техника Преодоления без учителя, бафы пути и техники
    # Преодоления, огромное влияние и массовая вербовка.
    BLOODLINE_GAPRYONG: (
        _e(stat_floor=RANK_INDEX["S"], influence_bonus=0.05, recruit_influence_cut=0.10),
        _s(None, {"recruit_quantity": 0.25}, grant_overcome=True),
        _s({"overcome": 0.10}, {"influence_bonus": 0.05}),
        _e(stat_floor=RANK_INDEX["S+"], recruit_influence_cut=0.15, recruit_cap=50),
        _s({"influence_power": 0.02}, resonance_bonus=0.50),
        _s({"durability": 0.06}, {"recruit_quantity": 0.25, "influence_rank_cut": 0.10}),
        _e(stat_floor=RANK_INDEX["SS"], influence_bonus=0.10),
        _s({"overcome": 0.15}, {"recruit_influence_cut": 0.15, "recruit_cap": 100}),
        _s({"influence_gap": 0.05}, {"influence_rank_cut": 0.15}, resonance_bonus=0.50),
        _s({"overcome": 0.20}, {"stat_floor": RANK_INDEX["SSS"], "influence_bonus": 0.30, "recruit_quantity": 0.50, "recruit_cap": 250}),
    ),
    # Ямадзаки: чёрные кости (прочность, первый удар по армии не проходит), усиление Киокушинкая и Ультра
    # инстинкт: всё само (вербовка, тренировки, школы, крутка, на вершине боссы), каждый пункт выключается.
    BLOODLINE_YAMAZAKI: (
        _c(durability=0.10, first_hit_ward=0.25),
        _e(auto_recruit=True),
        _s({"pierce": 0.05}, boost_kyokushin=0.15),
        _c(first_hit_ward=0.25, durability=0.05),
        _s({"durability": 0.10}, {"auto_train": True}),
        _c(first_hit_ward=0.25, reduction=0.05),
        _s(None, {"auto_school": True}, boost_kyokushin=0.20, training_kpd_boost=0.15),
        _s({"durability": 0.10}, {"auto_roll": True}),
        _s({"first_hit_ward": 0.25}, boost_kyokushin=0.25),
        _s({"durability": 0.10, "reduction": 0.03}, {"auto_boss": True}),
    ),
    # Самдака: контрпик капа тренировки. Статист растёт выше капа (до ×2), игрок сам решает, когда ему
    # переходить на следующий ранг, и может запретить переход. Вся родословная про тренировки.
    BLOODLINE_SAMDAK: (
        _e(extras_training=3, dev_points=0.10),
        _e(rank_hold=True, personal_cooldown=0.05),
        _e(extras_training_cooldown=0.10, training_cap_mult=0.25),
        _e(extras_coverage=5, personal_cooldown=0.10),
        _e(training_cap_mult=0.25, extras_training=3),
        _s(None, {"mastery_delay": 0.20, "stat_cost_discount": 0.08}, training_kpd_boost=0.25),
        _e(training_cap_mult=0.25, extras_extra_roll=0.10),
        _e(extras_training_cooldown=0.10, dev_points=0.15),
        _e(extras_coverage=5, extras_extra_roll=0.10, stat_cost_discount=0.08),
        _e(training_cap_mult=0.25, extras_training=5, dev_points=0.25, mastery_delay=0.20),
    ),
    # Александровых: контратаки и терпение. Контратака и отражение, пока терпишь — урон гасится, с каждым
    # раундом статисты и уники сильнее. Лучше всего с путём Адаптации.
    BLOODLINE_SOPHIA: (
        _c(counter=0.04, reflect=0.05),
        _c(adapt_threshold=0.35, adapt_bonus=0.25, endure_guard=0.01),
        _c(counter_power=0.10, endure_unique=0.03),
        _c(counter=0.04, endure_attack=0.02, cqc_boost=0.10),
        _c(adapt_bonus=0.25, adapt_guard=0.05),
        _c(reflect=0.05, endure_guard=0.01),
        _c(endure_attack=0.02, counter=0.04, adapt_threshold=0.30, cqc_accel=0.5),
        _s({"counter_power": 0.10, "endure_unique": 0.04}, adaptation_gauge_speed=0.50),
        _c(endure_guard=0.01, adapt_guard=0.05),
        _s({"endure_attack": 0.04, "counter": 0.03, "counter_power": 0.20, "endure_unique": 0.05, "cqc_boost": 0.15, "cqc_accel": 0.5}, adaptation_gauge_boost=0.25),
    ),
    # Куроды: ниндзя. Скрытность и безопасность, ложные данные для чужой разведки, разведка, шпионы и
    # саботаж сильнее, усиление техники Ниндзюцу.
    BLOODLINE_KURODA: (
        _s(None, {"stealth": True}, boost_ninjutsu=0.10),
        _e(security=1, sabotage_chance=0.05),
        _s({"dodge": 0.03}, {"false_intel": 0.15}),
        _e(scout=1, sabotage_cooldown=0.15),
        _s(None, {"spy_chance": 0.10}, boost_ninjutsu=0.15),
        _e(silent_sabotage=True, security=1),
        _e(false_intel=0.15, sabotage_loot=0.15),
        _s({"first_strike": 0.02}, {"spy_resist": 0.15, "logs": 1}),
        _s(None, {"sabotage_chance": 0.07, "scout": 2}, boost_ninjutsu=0.25),
        _s({"first_strike": 0.03}, {"security": 2, "false_intel": 0.20, "spy_chance": 0.15, "spy_resist": 0.15, "scout": 3}),
    ),
    # Джинчоля: игра через контракты и вербовку. Контракты дешевле, вместе с купленными приходят бесплатные,
    # часть выживших остаётся навсегда, вербовка приводит больше бойцов.
    BLOODLINE_JINCHEOL: (
        _e(contract_discount=0.10, contract_retain=0.01),
        _e(recruit_quantity=0.25),
        _e(contract_bonus=0.10, recruit_cap=5),
        _e(contract_discount=0.10, recruit_cooldown=0.15),
        _e(contract_retain=0.01, contract_duration=0.25),
        _e(recruit_rank_bonus=1, contract_bonus=0.10),
        _s({"attack": 0.04}, {"contract_discount": 0.10}),
        _e(contract_retain=0.01, recruit_quantity=0.25),
        _e(contract_bonus=0.15, recruit_cap=25),
        _e(contract_discount=0.15, contract_retain=0.02, contract_bonus=0.15, recruit_rank_bonus=1),
    ),
    # Хансу: обучение. Быстрее личные тренировки, тренировки статистов и занятия школ, сильнее все техники,
    # учатся дешевле и быстрее, часть заданий учителя засчитывается сама.
    BLOODLINE_HANSU: (
        _s(None, {"dev_points": 0.10, "tech_fragment_discount": 0.05}, boost_all_techniques=0.03),
        _e(personal_cooldown=0.10, extras_training_cooldown=0.10),
        _e(technique_quest_speed=0.10, school_cooldown=0.10),
        _s(None, {"mastery_delay": 0.15}, boost_all_techniques=0.04),
        _e(auto_tech_task=1, tech_fragment_discount=0.10),
        _e(personal_cooldown=0.10, extras_training_cooldown=0.10, school_cooldown=0.10),
        _s(None, {"technique_quest_speed": 0.15}, boost_all_techniques=0.05),
        _e(dev_points=0.15, tech_fragment_discount=0.10),
        _e(personal_cooldown=0.10, extras_training_cooldown=0.10, school_cooldown=0.10),
        _s(None, {"auto_tech_task": 1, "technique_quest_speed": 0.15, "tech_fragment_discount": 0.15, "dev_points": 0.25}, boost_all_techniques=0.08),
    ),
}

LEVELS[BLOODLINE_PENGUAN] = (
    # Пеньгуана (пользователь 2026-11-13): игра через доход. Сила, влияние и доход растут от
    # богатства (доход, районы, города — `services/penguan.wealth`); каждый уровень — своя механика.
    _s(eco={"income": 0.05}, pg_attack=0.03),  # Деньги — сила: +атака от богатства
    _e(contract_duration=0.5, contract_power=0.15),  # Золотые наёмники
    _s(pg_bribe=0.08),  # Подкуп: на час реакции врага слабее
    _s(pg_land_income=0.01, pg_city_income=0.02, pg_influence=0.02),  # Земля кормит, деньги — влияние
    _s(pg_constructor=0.03),  # Конструктор статистов: до 3% мощи армии в сутки
    _s(pg_chest=0.08, pg_bribe=0.04),  # Военная казна: на час +атака
    _s(pg_recruit=0.5),  # Золотая вербовка: на час +50% бойцов
    _s(pg_buyback=0.25),  # Выкуп павших: до 25% последнего боя
    _s(pg_buyout=1),  # Выкуп района бота без боя
    _s(  # Монополия и вершина: всё сильнее
        eco={"income": 0.10},
        pg_attack=0.03, pg_influence=0.02, pg_constructor=0.03, pg_buyback=0.15, pg_chest=0.07,
        pg_bribe=0.08, pg_recruit=0.5, pg_monopoly=0.5, pg_monopoly_share=0.3,
    ),
)

# Множители баланса — подобраны симуляцией 2026-11-14 (30 билдов уровня Никиты, турнир на настоящем движке боя,
# ~1.5 млн боёв). Умножают боевые числа уровней при загрузке (`config/development.scale_levels`): тексты и бой видят
# одно и то же. Пользователь: слабое — сильнее, перекачанное — слабее, экономические специализации не трогать.
BLOODLINE_BALANCE: dict[str, float] = {
    BLOODLINE_MUJIN: 0.55,
    BLOODLINE_YAMAZAKI: 1.2,
    BLOODLINE_SOPHIA: 1.1,
    BLOODLINE_KURODA: 1.3,
}
LEVELS = scale_levels(LEVELS, BLOODLINE_BALANCE)


BLOODLINE_START_LEVEL = 1  # даётся при выборе


def bloodline_level_cost(next_level: int) -> int:
    """Капли крови за уровень: 2-й — 3, 3-й — 5 … 10-й — 17 (всего 80). Капли редкие (боссы,
    позже пробуждение) — родословная качается месяцами (пользователь: «много патчей»)."""
    return 3 + 2 * (next_level - 2)
