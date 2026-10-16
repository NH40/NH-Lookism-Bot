"""Гениальности — 10 видов по 10 уровней (конфиг). Формат уровней — `config/development`.

Пользователь 2026-10-02: первая гениальность — случайно при регистрации, остаётся навсегда;
новые — прокрутом в магазине за фрагменты + NHCoin (повтор — крутка потеряна); активна
одна, свапается; качаются фрагментами с босса Элиты. Названы: бизнеса, войны, тренировок,
оружия (на уникальные техники), медиа (доходы), хакинга (взлом, шпионаж), наблюдения
(логи игроков), медицины; «всего 10» — автор кода добавил тактики и харизмы.

Каждый уровень — новая грань, а не просто «+%»: числа и смысл — решение автора кода
(«соблюдай баланс»). Тексты уровней — `texts/genius`.
"""
from __future__ import annotations

from bot.constant.genius import (
    GENIUS_BUSINESS,
    GENIUS_CHARISMA,
    GENIUS_HACKING,
    GENIUS_MEDIA,
    GENIUS_MEDICINE,
    GENIUS_OBSERVATION,
    GENIUS_TACTICS,
    GENIUS_TRAINING,
    GENIUS_WAR,
    GENIUS_WEAPONS,
)


def _c(**kw) -> dict:
    return {"combat": kw}


def _e(**kw) -> dict:
    return {"eco": kw}


def _ce(combat: dict, eco: dict) -> dict:
    return {"combat": combat, "eco": eco}


LEVELS: dict[str, tuple[dict, ...]] = {
    GENIUS_BUSINESS: (
        _e(income=0.05),
        _e(build_discount=0.10),
        _e(storage_hours=6),
        _e(upgrade_discount=0.10),
        _e(income=0.05),
        _e(tax_relief=0.15),
        _e(build_discount=0.10, upgrade_discount=0.10),
        _e(storage_hours=12),
        _e(income=0.07, tax_relief=0.15),
        _e(income=0.10, tax_relief=0.20),
    ),
    GENIUS_WAR: (
        _c(attack=0.03),
        _e(battle_cooldown=0.10),
        _e(recruit_rank_bonus=1),
        _c(suppress=0.05),
        _c(attack=0.03),
        _c(loss_save=0.05),
        _c(first_strike=0.03),
        _e(battle_cooldown=0.10),
        _e(recruit_rank_bonus=1),
        _c(attack=0.06, crit_chance=0.10),
    ),
    GENIUS_TRAINING: (
        _e(dev_points=0.10),
        _e(personal_cooldown=0.10),
        _e(extras_training=2),
        _e(stat_cost_discount=0.10),
        _e(dev_points=0.10),
        _e(extras_training_cooldown=0.15),
        _e(mastery_delay=0.25),
        _e(extras_training=3),
        _e(personal_cooldown=0.10),
        _e(dev_points=0.20, stat_cost_discount=0.10),
    ),
    GENIUS_WEAPONS: (
        _e(technique_power=0.05),
        _c(crit_power=0.10),
        _e(technique_power=0.05),
        _c(pierce=0.05),
        _e(fragment_bonus=0.10),
        _e(technique_power=0.05),
        _c(crit_chance=0.05),
        _e(technique_power=0.05),
        _c(pierce=0.05),
        _e(technique_power=0.15),
    ),
    GENIUS_MEDIA: (
        _e(income=0.04),
        _e(recruit_double=0.05),
        _e(income=0.04),
        _e(ticket_regen=0.10),
        _e(income=0.05),
        _e(recruit_double=0.05),
        _e(gacha_free_roll=0.05),
        _e(income=0.06),
        _e(ticket_cap=2),
        _e(income=0.10, gacha_luck=0.03),
    ),
    GENIUS_HACKING: (
        _e(scout=1),
        _e(sabotage_chance=0.05),
        _e(sabotage_loot=0.10),
        _e(scout=2),
        _e(sabotage_cooldown=0.15),
        _e(sabotage_chance=0.05),
        _e(scout=3),
        _e(sabotage_loot=0.20),
        _e(sabotage_cooldown=0.15),
        _e(silent_sabotage=True, sabotage_chance=0.05),
    ),
    GENIUS_OBSERVATION: (
        _e(logs=1),
        _e(marks=1),
        _e(logs=2),
        _e(marks=1),
        _e(scout=1),
        _e(logs=3),
        _e(marks=1),
        _c(dodge=0.03),
        _e(marks=2),
        _ce({"counter": 0.03}, {"foresight": 2}),
    ),
    # Гений медицины (2026-10-04): кроме боевой медицины — зелья. Открывает тиры III–VII,
    # удешевляет, продлевает и усиливает зелья, даёт слоты авто-зелий (`config/potion`).
    GENIUS_MEDICINE: (
        _ce({"loss_save": 0.03}, {"potion_tier": 3, "potion_discount": 0.03}),
        _ce({"heal": 0.03}, {"potion_discount": 0.03, "potion_duration": 0.05}),
        _ce({"loss_save": 0.03}, {"potion_tier": 4, "potion_discount": 0.03}),
        _ce({"heal": 0.03}, {"potion_discount": 0.03, "potion_duration": 0.05, "potion_power": 0.05}),
        _ce({"durability": 0.05}, {"potion_tier": 5, "potion_discount": 0.03}),
        _ce({"loss_save": 0.04}, {"potion_auto": 1, "potion_discount": 0.03, "potion_duration": 0.05}),
        _ce({"heal": 0.04}, {"potion_tier": 6, "potion_discount": 0.03, "potion_power": 0.05}),
        _ce({"reduction": 0.03}, {"potion_auto": 2, "potion_discount": 0.03, "potion_duration": 0.05}),
        _ce({"loss_save": 0.05}, {"potion_discount": 0.03, "potion_power": 0.05}),
        _ce({"heal": 0.06, "loss_save": 0.05}, {"potion_tier": 7, "potion_auto": 3, "potion_discount": 0.03, "potion_duration": 0.10, "potion_power": 0.10}),
    ),
    GENIUS_TACTICS: (
        _c(opening=0.10),
        _c(dodge=0.02, block=0.02),
        _c(rush=0.10, rush_rounds=2),
        _c(suppress=0.05),
        _c(opening=0.10),
        _c(counter=0.03),
        _c(first_strike=0.03),
        _c(rush=0.10, rush_rounds=3),
        _c(suppress=0.05),
        _ce({"opening": 0.20}, {"foresight": 1}),
    ),
    GENIUS_CHARISMA: (
        _e(recruit_double=0.05),
        _e(gacha_luck=0.02),
        _e(recruit_cooldown=0.10),
        _e(ticket_cap=1),
        _e(recruit_double=0.05),
        _e(gacha_luck=0.03),
        _e(ticket_regen=0.10),
        _e(recruit_rank_bonus=1),
        _e(gacha_free_roll=0.05),
        _e(recruit_double=0.10, gacha_luck=0.05),
    ),
}

# Прокачка: цена следующего уровня во фрагментах гениальности (уровень 1 — даром).
GENIUS_LEVEL_COST_PER_LEVEL = 15  # 2-й — 30, 10-й — 150; до 10-го — 810 фрагментов


def genius_level_cost(next_level: int) -> int:
    return GENIUS_LEVEL_COST_PER_LEVEL * next_level


# Прокрут новой гениальности в магазине (пользователь: «за фрагменты и деньги»).
GENIUS_ROLL_FRAGMENTS = 60
GENIUS_ROLL_COINS = 25_000
# Свап активной гениальности — не чаще раза в N секунд (не переключать перед каждым боем).
GENIUS_SWAP_COOLDOWN_SECONDS = 15 * 60
