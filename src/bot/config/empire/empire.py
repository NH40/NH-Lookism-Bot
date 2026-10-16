"""Император — налоги (конфиг).

Пользователь 2026-10-01 (`docs/design/fist_emperor.md`): император пассивно получает +10% от
дохода игроков своей страны (игрок их НЕ теряет) и устанавливает налог 10–50% — общий и
персональный (его игрок теряет, он уходит императору).
"""
from __future__ import annotations

from bot.constant.empire import SABOTAGE_STATISTS, SABOTAGE_TREASURY, SABOTAGE_UNIQUE

EMPIRE_TAX_MIN_PERCENT = 10
EMPIRE_TAX_MAX_PERCENT = 50
EMPIRE_TAX_DEFAULT_PERCENT = 10
EMPIRE_TAX_STEPS: tuple[int, ...] = (10, 20, 30, 40, 50)  # кнопки ставки на экране империи
EMPEROR_PASSIVE_BONUS_PERCENT = 10  # «сверху», у игрока не вычитается
EMPIRE_OVERRIDES_SHOWN = 10  # сколько персональных ставок показать на экране

# --- Саботаж снизу (пользователь 2026-10-01: фиксированный шанс, провал — только КД,
# переманить можно только уника, не стоящего на позиции). Числа — решение автора кода. ---
SABOTAGE_COOLDOWN_SECONDS = 12 * 60 * 60  # общий КД на любую попытку (успех или провал)
SABOTAGE_CHANCE_PERCENT: dict[str, int] = {
    SABOTAGE_STATISTS: 30,
    SABOTAGE_UNIQUE: 15,
    SABOTAGE_TREASURY: 25,
}
# Статисты: доля ОДНОЙ случайной стопки императора; но не больше, чем своих статистов у
# саботажника (не меньше пола) — иначе новичок одной удачей уносил бы миллиарды.
SABOTAGE_STATISTS_PERCENT = 5
SABOTAGE_STATISTS_FLOOR = 100
# Казна: доля кошелька NHCoin императора, с потолком за одну кражу.
SABOTAGE_TREASURY_PERCENT = 3
SABOTAGE_TREASURY_CAP = 100_000
SABOTAGE_RECENT_HOURS = 24  # «диверсий за сутки» на экране империи


# --- Война императоров (пользователь 2026-10-01/02: вызов с окном принятия, города —
# случайные, без городов — в банду; число городов и доля казны — от перевеса мощи, баланс
# доверен автору кода). ---
EMPIRE_WAR_ACCEPT_SECONDS = 60 * 60  # окно принятия (Скорость нападающего сокращает)
EMPIRE_WAR_COOLDOWN_SECONDS = 24 * 60 * 60  # нападающему — после объявления
EMPIRE_WAR_SHIELD_SECONDS = 12 * 60 * 60  # защитнику — после итога войны на него не напасть
EMPIRE_WAR_TREASURY_MAX_PERCENT = 50  # равные силы
EMPIRE_WAR_TREASURY_MIN_PERCENT = 10  # большой перевес
EMPIRE_WAR_BIG_GAP_RATIO = 3.0  # перевес (мощь победителя / проигравшего), с которого доля — минимум
EMPIRE_WAR_CITIES_PER_RATIO = 2  # +2 города за каждую единицу перевеса сверх равенства
# Пользователь 2026-10-13: «слишком много городов за один бой — от 3 до 8, не более».
EMPIRE_WAR_CITIES_MIN = 3
EMPIRE_WAR_CITIES_MAX = 8
EMPIRE_WAR_TARGETS_PAGE_SIZE = 10
EMPIRE_WAR_HISTORY_SHOWN = 5  # последних войн на экране империи в Mini App
EMPIRE_WAR_SWEEP_BATCH = 50


def war_treasury_percent(ratio: float) -> int:
    """Доля казны проигравшего: равные силы — 50%, перевес ×3 и больше — 10%, между —
    линейно (пользователь: «большая разница — 10%, максимально близкая — 50%»)."""
    ratio = min(max(ratio, 1.0), EMPIRE_WAR_BIG_GAP_RATIO)
    span = EMPIRE_WAR_TREASURY_MAX_PERCENT - EMPIRE_WAR_TREASURY_MIN_PERCENT
    return round(EMPIRE_WAR_TREASURY_MAX_PERCENT - span * (ratio - 1) / (EMPIRE_WAR_BIG_GAP_RATIO - 1))


def war_cities(ratio: float) -> int:
    """Сколько городов забирает победивший нападающий: растёт с перевесом, но всегда от 3 до 8
    (пользователь 2026-10-13). ×1–×2 → 3, ×3 → 5, ×4.5 и больше → 8; не больше, чем есть у
    проигравшего (обрезает сервис)."""
    raw = 1 + int((max(ratio, 1.0) - 1) * EMPIRE_WAR_CITIES_PER_RATIO)
    return max(EMPIRE_WAR_CITIES_MIN, min(EMPIRE_WAR_CITIES_MAX, raw))
