"""Картинки уников — отправка с кэшем Telegram `file_id` в Redis (приём UAP).

Пока используются старые карточки 1.0 из `assets/card/` (пользователь заменит их там же,
по тем же путям или перегенерировав каталог). Первая отправка загружает файл, Telegram
возвращает `file_id` — дальше карточка уходит мгновенно, без повторной загрузки.
"""
from __future__ import annotations

from aiogram.types import FSInputFile, Message
from redis.asyncio import Redis

from bot.cache.keys import card_photo_file_id
from bot.config.card import ASSETS_DIR, CardDef

# Запасной срок жизни ключа: file_id у Telegram не истекает, TTL — только чтобы не копить
# ключи удалённых карт.
_FILE_ID_TTL_SECONDS = 30 * 24 * 3600


def _version(card: CardDef) -> str | None:
    if not card.image:
        return None
    path = ASSETS_DIR / card.image
    try:
        stat = path.stat()
    except OSError:
        return None
    return f"{stat.st_mtime_ns}-{stat.st_size}"


async def get_card_photo(redis: Redis, card: CardDef) -> str | FSInputFile | None:
    """`file_id` из кэша или файл с диска; None — у карты нет картинки (шлём текстом)."""
    version = _version(card)
    if version is None:
        return None
    cached = await redis.get(card_photo_file_id(card.code, version))
    return cached or FSInputFile(ASSETS_DIR / card.image)


async def remember_card_photo(redis: Redis, card: CardDef, sent: Message | None) -> None:
    """Кэширует file_id после отправки/редактирования сообщения с фото карты."""
    version = _version(card)
    if version is None or sent is None or not sent.photo:
        return
    await redis.set(card_photo_file_id(card.code, version), sent.photo[-1].file_id, ex=_FILE_ID_TTL_SECONDS)
