"""Родословные — 10 веток по 10 уровней (конфиг). Формат уровней — `config/development`.

Пользователь 2026-10-02: родословная выбирается один раз навсегда (смена — донатом),
пробуждается каплями крови «на протяжении многих патчей»; «каждый уровень — чуть ли не
новая механика». Направления веток — от пользователя (`docs/design/development_systems.md`,
«Направления 10 родословных»), раскладка по уровням и числа — автор кода.

Уровень 1 даётся сразу при выборе (иначе выбор родословной ничего бы не значил до первых
капель), уровни 2–10 — за капли крови (`bloodline_level_cost`).
"""
from __future__ import annotations

from bot.constant.bloodline import (
    BLOODLINE_ELITE,
    BLOODLINE_GAPRYONG,
    BLOODLINE_HANSU,
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
    # Элиты: бизнес (развитие, ускорение, доход) и вербовка уникальных персонажей.
    BLOODLINE_ELITE: (
        _e(income=0.05),
        _e(gacha_luck=0.02),
        _e(upgrade_discount=0.10),
        _e(ticket_regen=0.10),
        _e(storage_hours=6, build_discount=0.10),
        _e(ticket_cap=2),
        _e(income=0.07),
        _e(gacha_free_roll=0.05),
        _e(tax_relief=0.15),
        _e(income=0.10, gacha_luck=0.05),
    ),
    # Муджина: огромнейшая сила, пик физической силы — мощь самой армии.
    BLOODLINE_MUJIN: (
        _e(army_power=0.05),
        _c(crit_power=0.20),
        _e(army_power=0.05),
        _c(pierce=0.05),
        _c(opening=0.20),
        _e(army_power=0.07),
        _c(durability=0.08),
        _c(crit_chance=0.05),
        _e(army_power=0.08),
        _s({"pierce": 0.10}, {"army_power": 0.12}),
    ),
    # Джинена: повышенные коэффициенты, дешёвый гений медицины, «Копирование» в бою:
    # уникальная техника → родословная → путь противника; усиливает путь Копирования.
    BLOODLINE_JINYEONG: (
        _s({"attack": 0.02, "durability": 0.02}, {"medicine_discount": 0.20}),
        _s(copy_path_boost=0.15),
        _s(copy_sources=(SOURCE_TECHNIQUE,), copy_strength=0.25),
        _c(attack=0.03, durability=0.03, dodge=0.02),
        _e(medicine_discount=0.20),
        _s(copy_sources=(SOURCE_TECHNIQUE, SOURCE_BLOODLINE), copy_strength=0.10),
        _s(copy_path_boost=0.20),
        _c(attack=0.03, durability=0.03),
        _s(copy_sources=(SOURCE_TECHNIQUE, SOURCE_BLOODLINE, SOURCE_PATH), copy_strength=0.10),
        _s(copy_strength=0.15, copy_path_boost=0.25),
    ),
    # Ким Гапрена: огромные базовые характеристики (старт примерно с S), уникальная техника
    # Преодоления без учителя, бафы пути и техники Преодоления («три камня»).
    BLOODLINE_GAPRYONG: (
        _e(stat_floor=RANK_INDEX["S"]),
        _s(grant_overcome=True),
        _c(overcome=0.10),
        _e(stat_floor=RANK_INDEX["S+"]),
        _s(resonance_bonus=0.50),
        _c(durability=0.06),
        _e(stat_floor=RANK_INDEX["SS"]),
        _c(overcome=0.15),
        _s(resonance_bonus=0.50),
        _s({"overcome": 0.20}, {"stat_floor": RANK_INDEX["SSS"]}),
    ),
    # Ямадзаки: чёрные кости (прочность, урон не доходит), Ультра инстинкт (автоматика:
    # вербовка → тренировка → крутка тикетов), Киокушинкай карате (пробитие).
    BLOODLINE_YAMAZAKI: (
        _c(durability=0.08),
        _e(auto_recruit=True),
        _c(pierce=0.08),
        _c(reduction=0.06),
        _e(auto_train=True),
        _c(durability=0.10),
        _c(pierce=0.10, counter=0.03),
        _e(auto_roll=True),
        _c(reduction=0.08, durability=0.10),
        _c(reduction=0.10, pierce=0.10),
    ),
    # Самдака: обучение — очки развития, доступ к мастерству быстрее, тренировки.
    BLOODLINE_SAMDAK: (
        _e(dev_points=0.10),
        _e(personal_cooldown=0.10),
        _e(mastery_delay=0.20),
        _e(stat_cost_discount=0.08),
        _e(extras_training=3),
        _e(dev_points=0.10),
        _e(mastery_delay=0.20),
        _e(personal_cooldown=0.10),
        _e(stat_cost_discount=0.08),
        _e(dev_points=0.20, extras_extra_roll=0.10),
    ),
    # Софии: читать противника, терпеть — и ударить; контрудары.
    BLOODLINE_SOPHIA: (
        _c(counter=0.04),
        _c(adapt_threshold=0.35, adapt_bonus=0.25),
        _c(adapt_guard=0.05),
        _c(counter=0.04),
        _c(adapt_bonus=0.25),
        _c(reflect=0.05),
        _c(adapt_threshold=0.30),
        _c(counter=0.05),
        _c(adapt_guard=0.06),
        _c(adapt_bonus=0.50, counter=0.05),
    ),
    # Куроды: ниндзя — скрытность (топы, отчёты, разведка), саботаж и шпионаж сильнее.
    BLOODLINE_KURODA: (
        _e(stealth=True),
        _e(sabotage_chance=0.05),
        _c(dodge=0.03),
        _e(sabotage_cooldown=0.15),
        _e(scout=1),
        _e(silent_sabotage=True),
        _e(sabotage_loot=0.15),
        _c(first_strike=0.02),
        _e(sabotage_chance=0.07),
        _s({"first_strike": 0.03}, {"scout": 2}),
    ),
    # Джинчоля: военный — вербовка лучше, контракты статистов дешевле и дольше.
    BLOODLINE_JINCHEOL: (
        _e(recruit_rank_bonus=1),
        _e(contract_discount=0.15),
        _e(recruit_cooldown=0.15),
        _e(contract_duration=0.25),
        _e(recruit_double=0.10),
        _e(recruit_rank_bonus=1),
        _e(contract_discount=0.15),
        _c(attack=0.04),
        _e(contract_duration=0.25, recruit_double=0.10),
        _e(recruit_rank_bonus=2, contract_discount=0.20),
    ),
    # Хансу: хаос — статисты действуют хаотичнее, бой ломается.
    BLOODLINE_HANSU: (
        _c(chaos=0.05),
        _c(suppress=0.05),
        _c(chaos=0.05),
        _c(counter=0.03),
        _c(chaos=0.05),
        _c(crit_chance=0.05),
        _c(chaos=0.05),
        _c(suppress=0.05),
        _c(chaos=0.05),
        _c(chaos=0.10, suppress=0.10),
    ),
}

BLOODLINE_START_LEVEL = 1  # даётся при выборе


def bloodline_level_cost(next_level: int) -> int:
    """Капли крови за уровень: 2-й — 3, 3-й — 5 … 10-й — 17 (всего 80). Капли редкие (боссы,
    позже пробуждение) — родословная качается месяцами (пользователь: «много патчей»)."""
    return 3 + 2 * (next_level - 2)
