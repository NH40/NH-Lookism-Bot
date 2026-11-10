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

# Дань младших императоров (пользователь 2026-11-10, `services/empire/tribute`): % налога
# императоров той же страны в младших лигах; потолок за сутки — % собственного налога.
EMPIRE_TRIBUTE_PERCENT = 10
EMPIRE_TRIBUTE_CAP_PERCENT = 20
EMPIRE_TRIBUTE_SWEEP_SECONDS = 600

# --- Ивенты императора для подданных (пользователь 2026-11-10, `services/empire/events`).
# Всё оплачивает император из NHCoin заранее: раздачи, подарок, праздник и турнир — перевод
# подданным (остаток возвращается), сборы — монеты сгорают, каникулы — бесплатно (теряет налог).
# Новых денег в игре не появляется. Числа — решение автора кода, все в настройках админки. ---
EMPIRE_EVENT_CLAIM_HOURS = 24  # раздачи NHCoin и статистов: сколько можно забирать
EMPIRE_EVENT_DURATIONS_HOURS: tuple[int, ...] = (6, 12, 24)  # праздник, каникулы, сборы — кнопки
EMPIRE_EVENT_MAX_SLOTS = 1000  # раздачи: мест
EMPIRE_EVENT_MIN_FUND = 1_000  # минимум фонда праздника и турнира, NHCoin
EMPIRE_GIFT_COINS_PER_POWER = 10  # раздача статистов: NHCoin за 1 мощи статиста (контракт на сутки — 2)
# Ранг раздачи — не выше потолка банд (`recruit.PHASE_RANK_CAP_INDEX`): иначе император выдавал бы
# бандам ранги, которые им недоступны ни вербовкой, ни контрактами.
EMPIRE_GIFT_MAX_RANK = "EX"
EMPIRE_FEAST_INCOME_PERCENT = 25  # праздник: +% к доходу подданных, выплачивается из фонда
EMPIRE_DRILL_CD_PERCENT = 30  # сборы: −% к КД личной тренировки и тренировки статистов
# Сборы: цена за одного подданного (заходил за сутки) за час — по лиге императора (2 поколение … Легенды).
EMPIRE_DRILL_PRICE_PER_SUBJECT_HOUR: tuple[int, ...] = (500, 5_000, 200_000, 200_000, 3_000_000)
EMPIRE_TOURNAMENT_HOURS = 24
EMPIRE_TOURNAMENT_SHARES: tuple[int, ...] = (50, 30, 20)  # % фонда за 1–3 место по победам в PvP
EMPIRE_DAILY_GIFT_MAX_DAYS = 7
EMPIRE_EVENT_SWEEP_SECONDS = 60
# Перезарядка вида ивента от запуска, ч.
EMPIRE_EVENT_COOLDOWN_HOURS: dict[str, int] = {
    "coins": 6, "statists": 6, "feast": 24, "holiday": 24, "drill": 24, "tournament": 24, "daily": 24,
}

# Объявления императора (пользователь 2026-11-06: раз в 4 часа, значение меняется в админке).
EMPIRE_ANNOUNCE_COOLDOWN_SECONDS = 4 * 60 * 60
EMPIRE_ANNOUNCE_MAX_CHARS = 1000
EMPIRE_ANNOUNCE_BATCH_SIZE = 25  # темп рассылки в лимитах Telegram
EMPIRE_ANNOUNCE_BATCH_PAUSE_SECONDS = 1
# 3 объявления по 1000 символов с заголовками умещаются в лимит сообщения Telegram (4096).
EMPIRE_ANNOUNCE_LOG_PAGE_SIZE = 3
EMPIRE_ANNOUNCE_SENT_SHOWN = 3  # последних объявлений на экране императора

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
# 2026-11-10 (пользователь): КД нападения и щит — по лиге (индекс — лига: 2 поколение … Легенды).
# Щит получает ТОЛЬКО проигравший — нападал он или защищался; победитель без щита. Под щитом
# сам нападать может, на него — нет. КД нападающего — по его лиге, щит — по лиге проигравшего.
EMPIRE_WAR_COOLDOWN_BY_LEAGUE_SECONDS: tuple[int, ...] = (4 * 3600, 3 * 3600, 2 * 3600, 90 * 60, 3600)
EMPIRE_WAR_SHIELD_BY_LEAGUE_SECONDS: tuple[int, ...] = (6 * 3600, 5 * 3600, 4 * 3600, 3 * 3600, 2 * 3600)
# Ловкость в войне (вторая атака без КД): шанс ниже, чем в обычных боях — нужна большая ловкость.
EMPIRE_WAR_FREE_ATTACK_FACTOR = 0.5
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


def war_cooldown_seconds(league: int) -> int:
    return EMPIRE_WAR_COOLDOWN_BY_LEAGUE_SECONDS[min(max(league, 0), len(EMPIRE_WAR_COOLDOWN_BY_LEAGUE_SECONDS) - 1)]


def war_shield_seconds(league: int) -> int:
    return EMPIRE_WAR_SHIELD_BY_LEAGUE_SECONDS[min(max(league, 0), len(EMPIRE_WAR_SHIELD_BY_LEAGUE_SECONDS) - 1)]


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
