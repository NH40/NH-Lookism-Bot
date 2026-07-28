"""Отправка меню атаки с опциональным фото карты страны вместо текста.

Telegram не даёт edit_text поверх фото-сообщения (и наоборот) — send_menu
сам решает, пересоздавать сообщение или редактировать текущее.
"""
from pathlib import Path
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message

_PROJECT_ROOT = Path(__file__).parent.parent.parent
CAPTION_LIMIT = 1024


async def send_menu(
    cb: CallbackQuery,
    text: str,
    kb: InlineKeyboardMarkup,
    photo_path: str | None = None,
) -> None:
    full_path = _PROJECT_ROOT / photo_path if photo_path else None
    if full_path and full_path.exists():
        caption = text if len(text) <= CAPTION_LIMIT else text[:CAPTION_LIMIT - 3] + "..."
        try:
            await cb.message.delete()
        except Exception:
            pass
        try:
            await cb.message.answer_photo(
                FSInputFile(str(full_path)), caption=caption, reply_markup=kb, parse_mode="HTML"
            )
            return
        except Exception:
            pass
        try:
            await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        return

    if getattr(cb.message, "photo", None):
        try:
            await cb.message.delete()
        except Exception:
            pass
        try:
            await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
    else:
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass


async def safe_edit(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup) -> None:
    """Text-only вариант send_menu — безопасная замена голому
    `cb.message.edit_text(...)` в try/except: если текущее сообщение фото
    (карта страны, карточка, босс и т.п.), удаляет его и отправляет текст
    новым сообщением вместо молчаливого no-op."""
    await send_menu(cb, text, kb, None)


async def safe_edit_message(message: Message, text: str, kb: InlineKeyboardMarkup) -> None:
    """Как safe_edit, но принимает Message напрямую вместо CallbackQuery —
    для хэндлеров, где под рукой уже нет объекта cb (например helper,
    переиспользуемый и командой /players, и callback-пагинацией)."""
    if getattr(message, "photo", None):
        try:
            await message.delete()
        except Exception:
            pass
        try:
            await message.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
    else:
        try:
            await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await message.answer(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass


async def safe_edit_get_message(
    cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None = None
):
    """Как safe_edit, но возвращает итоговое Message — нужно там, где код ПОСЛЕ
    редактирования должен знать актуальные chat_id/message_id (например, фоновая
    задача, которая позже отредактирует именно это сообщение результатом)."""
    if getattr(cb.message, "photo", None):
        try:
            await cb.message.delete()
        except Exception:
            pass
        return await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    try:
        return await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        return await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
