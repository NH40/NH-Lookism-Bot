"""Кланы (конфиг). Дизайн — `docs/design/clans.md`. Механику земель, зданий, роты и войн
пользователь доверил автору кода (2026-10-04) — числа здесь решение автора, их можно править.
Формат бафов зданий и донат-уровней — как у систем развития (`{"combat": …, "eco": …}`,
`services/build`)."""
from __future__ import annotations

from bot.constant.clan import (
    BUILDING_ALCHEMY,
    BUILDING_HUNTERS,
    BUILDING_RECRUIT,
    BUILDING_BARRACKS,
    BUILDING_DOJO,
    BUILDING_FORGE,
    BUILDING_LIBRARY,
    BUILDING_MARKET,
    BUILDING_TEMPLE,
    BUILDING_TRAINING,
    BUILDING_WALL,
    BUILDING_WATCHTOWER,
)

CLAN_MAX_MEMBERS = 15
CLAN_NAME_MIN = 3
CLAN_NAME_MAX = 24
CLAN_DESCRIPTION_MAX = 300
CLAN_PAGE = 10
CLAN_TOP_IMAGE = 10  # аватарку ставят кланы из топ-N (как в UAP)
# Создание клана — NHCoin (пользователь: «чтобы создать клан, необходимо энное количество денег»).
CLAN_CREATE_COST = 50_000

# --- Земли ---
CLAN_START_LANDS = 8
CLAN_BUY_LANDS_MAX = 16  # освоить за казну — до 16 (пользователь)
CLAN_LANDS_PER_DONATE_LEVEL = 4  # каждый донат-уровень +4 к потолку (пользователь)
CLAN_MIN_LANDS = 4  # война не опускает клан ниже
CLAN_LAND_PRICE_STEP = 30_000  # освоение n-й земли сверх стартовых: шаг × (n − 8)


def land_price(current_lands: int) -> int:
    """Цена освоения следующей земли."""
    return CLAN_LAND_PRICE_STEP * max(1, current_lands + 1 - CLAN_START_LANDS)


# --- Здания: вид → (потолок числа, базовая цена, бафы одного здания). Цена следующего —
# база × (1 + уже построено); снос возвращает половину цены последнего.
CLAN_BUILDINGS: dict[str, tuple[int, int, dict]] = {
    BUILDING_MARKET: (4, 40_000, {"eco": {"income": 0.03}}),
    BUILDING_TRAINING: (4, 35_000, {"eco": {"extras_training": 2}}),
    BUILDING_LIBRARY: (4, 35_000, {"eco": {"dev_points": 0.05}}),
    BUILDING_BARRACKS: (3, 60_000, {"eco": {"army_power": 0.02}}),
    BUILDING_TEMPLE: (2, 40_000, {"eco": {"gacha_luck": 0.02}}),
    BUILDING_WATCHTOWER: (3, 50_000, {}),  # клановые боссы на карте
    BUILDING_DOJO: (3, 50_000, {}),  # клановые учителя на карте
    BUILDING_FORGE: (3, 45_000, {}),  # атака роты в войне
    BUILDING_WALL: (3, 45_000, {}),  # защита роты в войне
    # 2026-10-12: сумма лимитов 38 ≥ 36 земель — каждой земле есть применение, выбор за кланом.
    BUILDING_ALCHEMY: (3, 45_000, {"eco": {"potion_discount": 0.04, "potion_duration": 0.05}}),
    BUILDING_HUNTERS: (3, 55_000, {"eco": {"fragment_bonus": 0.05}}),
    BUILDING_RECRUIT: (3, 40_000, {"eco": {"recruit_cooldown": 0.04}}),
}
CLAN_DEMOLISH_REFUND = 0.5


def building_price(kind: str, built: int) -> int:
    return CLAN_BUILDINGS[kind][1] * (1 + built)


# Война: бонусы роты за здание.
CLAN_FORGE_ATTACK = 0.05  # атака роты нападающего за Кузницу
CLAN_WALL_DEFENSE = 0.05  # прочность и гашение урона роты защитника за Стену

# Клановые события на карте: шанс появления за тик фонового прохода событий на одно здание
# (Сторожевая башня → босс, Додзё → учитель), живут столько же, сколько общие.
CLAN_BOSS_CHANCE_PER_TOWER = 0.5 * 300 / (5 * 60 * 60)  # одна башня ≈ раз в 10 ч
CLAN_TEACHER_CHANCE_PER_DOJO = 0.5 * 300 / (4 * 60 * 60)  # одно додзё ≈ раз в 8 ч

# --- Донат-уровни 1–5: бафы всем участникам (накопительно) и бонус роты в войне. Покупает любой
# участник за донат-коины; уровень привязан к купившему — ушёл из клана (сам, кик, удаление клана)
# → клан теряет уровень, игроку возвращается уплаченное (пользователь 2026-10-08). Клановый донат
# LBP 1.3 не переносится. Цена: 1 000, дальше +20% от первого за шаг (1 000…1 800, всего 7 000).
CLAN_DONATE_BASE_PRICE = 1_000
CLAN_DONATE_PRICE_STEP = 200


def clan_donate_price(level: int) -> int:
    return CLAN_DONATE_BASE_PRICE + CLAN_DONATE_PRICE_STEP * (level - 1)


CLAN_DONATE_LEVELS: tuple[dict, ...] = (
    {"eco": {"income": 0.02}, "combat": {"attack": 0.02}},
    {"eco": {"income": 0.02, "army_power": 0.01}, "combat": {"attack": 0.02}},
    {"eco": {"income": 0.02, "dev_points": 0.05}, "combat": {"attack": 0.03}},
    {"eco": {"income": 0.02, "army_power": 0.02}, "combat": {"attack": 0.03}},
    {"eco": {"income": 0.04, "gacha_luck": 0.02}, "combat": {"attack": 0.05}},
)

# --- Рота ---
CLAN_GARRISON_TENURE_HOURS = 24  # забирать из роты — через сутки после вступления

# --- Война ---
CLAN_WAR_COOLDOWN_HOURS = 24  # клан нападает раз в сутки (пользователь)
CLAN_WAR_SHIELD_HOURS = 6  # после нападения защитник под щитом
CLAN_WAR_TREASURY_PERCENT = 10  # победитель-нападающий забирает долю казны


def war_lands(ratio: float, defender_lands: int) -> int:
    """Сколько земель забирает победитель-нападающий: 10% при равенстве … 30% при перевесе ×3+,
    минимум 1; защитнику всегда остаётся `CLAN_MIN_LANDS`."""
    share = min(0.30, 0.10 + 0.10 * max(0.0, ratio - 1.0))
    return max(0, min(max(1, int(defender_lands * share)), defender_lands - CLAN_MIN_LANDS))


# --- Доход владельца и заместителя: доля от каждого зачисления дохода участника (сверху). ---
CLAN_OWNER_SHARE = 0.01
CLAN_DEPUTY_SHARE = 0.01

# --- Магазин клана (из казны): вид → (подпись-ключ, цена за участника). ---
# Тикеты всем участникам — любое количество, вводом числа (пользователь 2026-10-21: «как
# статистов, просто написав кол-во»): цена за тикет каждому участнику, паков больше нет.
CLAN_SHOP_TICKET_PRICE = 4_000
CLAN_SHOP_TICKETS_MAX = 1_000
CLAN_SHOP_POTION_TIERS: tuple[int, ...] = (1, 2, 3)  # зелья всем: тир → цена тира × участников
# Контракты в роту (пользователь 2026-10-12: вместо вечных наёмников — их забирали себе в обход
# контрактов). Цена за единицу мощи и срок — как у личных контрактов; забрать из роты нельзя.
CLAN_CONTRACT_COINS_PER_POWER = 2
CLAN_CONTRACT_HOURS = 24
CLAN_LOG_PAGE = 15
