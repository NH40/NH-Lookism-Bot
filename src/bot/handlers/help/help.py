"""Гайд `/help` — разделы по всем механикам бота (хендлеры).

Меню разделов → раздел (стрелки к соседним, «К разделам»). Без БД: чистый UI, тексты —
`texts/help`.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.constant.help import CB_HELP_OPEN, CB_HELP_SECTION_PREFIX
from bot.keyboards.help import help_menu, section_menu
from bot.texts.help import HELP_MENU, HELP_SECTION_BY_CODE
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
