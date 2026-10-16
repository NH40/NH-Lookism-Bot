"""Донат (конфиг). Пользователь 2026-10-08: донат продаёт ускорение развития, не боевую силу;
«куча маленьких донатов, а всё вместе — ровно 100 000 коинов» (1 коин = 1 ₽). Раздел по
системам выбран через AskUserQuestion: второе тело 10к, пути 40к, техники 30к, гений 20к.
Цены уровней растут линейно; последний (10-й) уровень добирает остаток, чтобы сумма сошлась.
"""
from __future__ import annotations

from bot.config.development import MAX_LEVEL
from bot.constant.genius import GENIUSES
from bot.constant.unique_path import PATHS
from bot.constant.unique_technique import TECHNIQUES

# Пополнение (ЮKassa через Telegram Payments, как в UAP).
DONATE_PRESETS_RUB: tuple[int, ...] = (100, 300, 500, 1000, 3000, 5000)
DONATE_MIN_RUB = 50
DONATE_MAX_RUB = 100_000

SECOND_BODY_PRICE = 10_000  # одно на аккаунт


def _ladder(unlock: int, step: int, total: int) -> tuple[int, dict[int, int]]:
    """(цена открытия, {уровень: цена}) для уровней 2..10: step×(уровень−1), 10-й — остаток."""
    levels = {lvl: step * (lvl - 1) for lvl in range(2, MAX_LEVEL)}
    levels[MAX_LEVEL] = total - unlock - sum(levels.values())
    return unlock, levels


# Итог на одну позицию: гений 2 000 (×10), путь 3 078 (×13), техника 2 726 (×11).
GENIUS_UNLOCK, GENIUS_LEVEL_PRICES = _ladder(200, 40, 2_000)
PATH_UNLOCK, PATH_LEVEL_PRICES = _ladder(400, 60, 3_078)
TECHNIQUE_UNLOCK, TECHNIQUE_LEVEL_PRICES = _ladder(300, 55, 2_726)


def full_price() -> int:
    """Стоимость «купить всё» — проверяется assert ниже."""
    def per(unlock: int, levels: dict[int, int]) -> int:
        return unlock + sum(levels.values())

    return (
        SECOND_BODY_PRICE
        + len(GENIUSES) * per(GENIUS_UNLOCK, GENIUS_LEVEL_PRICES)
        + len(PATHS) * per(PATH_UNLOCK, PATH_LEVEL_PRICES)
        + len(TECHNIQUES) * per(TECHNIQUE_UNLOCK, TECHNIQUE_LEVEL_PRICES)
    )


assert full_price() == 100_000, full_price()
assert all(p > 0 for d in (GENIUS_LEVEL_PRICES, PATH_LEVEL_PRICES, TECHNIQUE_LEVEL_PRICES) for p in d.values())

# Перенос доната LBP 1.3 (цены из `app/data/titles.py` 1.3 — git `93ad05f^`). Сумма = цена
# титулов + цена кругов чёрного рынка + остаток NHDonate (покупки шли С баланса, поэтому
# платежи отдельно не прибавляем — иначе двойной счёт). Титулы и круги, выданные админом,
# тоже считаются (так оформлялись продажи через менеджера — AskUserQuestion 2026-10-08).
# Клановые донаты 1.3 — отдельно, позже (пользователь).
LBP1_TITLE_PRICES: dict[str, int] = {
    "fist_power": 350, "romantic_recruit": 350, "great_influence": 100, "genius_training": 50,
    "genius_business": 200, "genius_weapon": 150, "genius_combat": 100, "genius_hacking": 80,
    "genius_medicine": 100, "genius_scale": 200, "legend_1gen": 250, "monster_training": 150,
    "reverse_eyes": 300, "selection": 350, "manager_fav": 400, "concentration": 300, "focus": 200,
    "raid_cd": 600, "duel_cd": 500, "ui_title": 1000, "ui_potion": 500, "rom_extra_skills": 500,
    "rom_max_chance": 400,
}
# Круг: (цена за круг, максимум кругов); сверх максимума цена росла ×1.5 за каждый следующий.
LBP1_CIRCLE_PRICES: dict[str, tuple[int, int]] = {
    "archangel": (1000, 10), "clan_head": (1200, 5), "korea_devil": (1200, 6), "mountain_lord": (1200, 4),
    "shadow": (1200, 5), "dragon": (1200, 6), "dungeon_lord": (800, 4), "emperor_circle": (1200, 10),
}


def lbp1_circles_cost(donat_id: str, circles: int) -> int:
    price, cap = LBP1_CIRCLE_PRICES.get(donat_id, (0, 0))
    return sum(price if i <= cap else round(price * 1.5 ** (i - cap)) for i in range(1, circles + 1))
