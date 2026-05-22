"""
Утилита для отправки карточки как Telegram-фото.
Кэширует file_id чтобы не загружать файл повторно.
"""
import pathlib
from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup

from app.data.card_images import get_image_path, get_cached_file_id, cache_file_id

_PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent


async def send_card_photo(
    bot: Bot,
    chat_id: int,
    char_name: str,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str = "HTML",
) -> bool:
    """
    Отправляет изображение карточки в чат.

    1. Смотрит в кэш (file_id) — если есть, отправляет без загрузки.
    2. Если нет кэша, загружает из локального файла и сохраняет file_id.
    3. Возвращает True если отправлено, False если изображения нет.
    """
    # ── Попытка через кэш ─────────────────────────────────────────────────────
    file_id = get_cached_file_id(char_name)
    if file_id:
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=file_id,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return True
        except Exception:
            pass  # file_id устарел → загружаем заново

    # ── Загрузка из файла ─────────────────────────────────────────────────────
    rel_path = get_image_path(char_name)
    if not rel_path:
        return False

    full_path = _PROJECT_ROOT / rel_path
    if not full_path.exists():
        return False

    try:
        msg = await bot.send_photo(
            chat_id=chat_id,
            photo=FSInputFile(str(full_path)),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        # Кэшируем file_id (берём самое большое разрешение)
        if msg.photo:
            cache_file_id(char_name, msg.photo[-1].file_id)
        return True
    except Exception:
        return False
