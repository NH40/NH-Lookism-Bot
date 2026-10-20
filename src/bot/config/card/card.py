"""Уникальные персонажи — каталог карт и шансы редкостей (конфиг).

Каталог — `cards_data.py`, генерируется `scripts/gen_card_config.py` из рабочей таблицы
пользователя `docs/design/unique_characters.md` (мощь и позиции). Навыков в каталоге пока
нет: их формулировки пользователь ещё распределяет, механика подключится отдельно.

Шансы редкостей подтверждены пользователем 2026-09-30 (раздел 3 документа): топ урезан
относительно 1.0 (вершина 0.25% вместо 1%) — тикетов до ~48 в сутки. Абсолюты — в обычной
крутке со сверхмалым шансом.
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from bot.constant.card import (
    RARITY_ABSOLUTE,
    RARITY_BOSS,
    RARITY_GEN_ZERO,
    RARITY_KING,
    RARITY_LEGEND,
    RARITY_MEMBER,
    RARITY_NEW_LEGEND,
    RARITY_PEAK,
    RARITY_STRONG_KING,
)


class CardDef(NamedTuple):
    code: str  # хранится в БД — не менять после релиза
    name: str
    rarity: str
    power: int  # мощь одной копии в бою
    positions: tuple[str, ...]  # допустимые позиции отряда
    image: str | None = None  # путь картинки относительно `assets/` (пока карточки 1.0)


# Корень ассетов: `assets/` в корне репозитория (в контейнере — `/app/assets`, смонтирован
# томом, чтобы замена картинок не требовала пересборки образа).
ASSETS_DIR = Path(__file__).resolve().parents[4] / "assets"

# Шанс крутки по редкости, % (сумма = 100).
# Массовое открытие тикетов вводом числа (пользователь 2026-10-21: у игроков 4–7 тыс. тикетов,
# «10 тысяч должны открываться легко»). Открытие пакетное (`services/gacha.roll_many`): одно
# списание, розыгрыш в памяти, одна запись на карту — 10 000 тикетов это ~десяток запросов.
GACHA_MASS_MAX = 10_000

RARITY_CHANCE_PERCENT: dict[str, float] = {
    RARITY_MEMBER: 45.04,
    RARITY_BOSS: 25.0,
    RARITY_KING: 15.0,
    RARITY_STRONG_KING: 8.0,
    RARITY_GEN_ZERO: 4.0,
    RARITY_NEW_LEGEND: 2.0,
    RARITY_LEGEND: 0.7,
    RARITY_PEAK: 0.25,
    RARITY_ABSOLUTE: 0.01,
}
