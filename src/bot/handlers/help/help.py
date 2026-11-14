"""Гайд `/help` — разделы по всем механикам бота (хендлеры).

Меню разделов → раздел (стрелки к соседним, «К разделам»). Без БД: чистый UI, тексты —
`texts/help`.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message

from bot.config.card.card import ASSETS_DIR
from bot.constant.help import CB_HELP_IMAGES_PREFIX, CB_HELP_OPEN, CB_HELP_SECTION_PREFIX
from bot.keyboards.help import help_menu, section_menu
from bot.texts.help import HELP_IMAGE_SECTIONS, HELP_IMAGES_MISSING, HELP_MENU, HELP_SECTION_BY_CODE
from bot.utils.safe_edit import safe_edit_text

router = Router(name="help")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_MENU, reply_markup=help_menu())


@router.callback_query(F.data == CB_HELP_OPEN)
async def cb_help_open(callback: CallbackQuery) -> None:
    await callback.answer()
    await safe_edit_text(callback.message, HELP_MENU, reply_markup=help_menu())


@router.callback_query(F.data.startswith(CB_HELP_SECTION_PREFIX))
async def cb_help_section(callback: CallbackQuery) -> None:
    section = HELP_SECTION_BY_CODE.get(callback.data.removeprefix(CB_HELP_SECTION_PREFIX))
    await callback.answer()
    if section is None:
        await safe_edit_text(callback.message, HELP_MENU, reply_markup=help_menu())
        return
    await safe_edit_text(callback.message, section[2], reply_markup=section_menu(section[0]))


@router.callback_query(F.data.startswith(CB_HELP_IMAGES_PREFIX))
async def cb_help_images(callback: CallbackQuery) -> None:
    """Листы родословных, путей, техник и гениальностей — альбомами по 10 (как в гайде Mini App)."""
    code = callback.data.removeprefix(CB_HELP_IMAGES_PREFIX)
    section = next((s for s in HELP_IMAGE_SECTIONS if s[0] == code), None)
    folder = ASSETS_DIR / "guide"
    files = sorted(folder.glob(f"{section[2]}-*.png"), key=lambda p: int(p.stem.rsplit("-", 1)[1])) if section and folder.is_dir() else []
    if not files:
        await callback.answer(HELP_IMAGES_MISSING, show_alert=True)
        return
    await callback.answer()
    for i in range(0, len(files), 10):
        chunk = files[i : i + 10]
        media = [InputMediaPhoto(media=FSInputFile(p), caption=f"{section[1]}. {section[3]}" if i == 0 and j == 0 else None)
                 for j, p in enumerate(chunk)]
        await callback.message.answer_media_group(media)
    await callback.message.answer(HELP_MENU, reply_markup=help_menu())
