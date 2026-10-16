"""Тренировки — личная (очки развития, КД 1 час) и тренировка статистов (3 этапа: прокачка мощи / пробуждение звёзд / повышение ранга) (клавиатуры)."""
from __future__ import annotations

from bot.constant.profile import CB_PROFILE_OPEN
from bot.texts.common import BTN_BACK_TO_PROFILE

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.training import CB_TRAIN_EXTRAS_RUN, CB_TRAIN_PERSONAL
from bot.texts.training import BTN_PERSONAL_TRAINING

BTN_TRAIN_EXTRAS_RUN = "🏋️ Тренировать статистов"


from bot.constant.training import CB_TRAIN_SCHOOLS_OPEN, CB_TRAIN_TECH_OPEN  # noqa: E402
from bot.texts.training import BTN_SCHOOLS, BTN_TECH_TRAINING  # noqa: E402

def train_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_PERSONAL_TRAINING, callback_data=CB_TRAIN_PERSONAL)],
            [InlineKeyboardButton(text=BTN_TRAIN_EXTRAS_RUN, callback_data=CB_TRAIN_EXTRAS_RUN)],
            [
                InlineKeyboardButton(text=BTN_TECH_TRAINING, callback_data=CB_TRAIN_TECH_OPEN),
                InlineKeyboardButton(text=BTN_SCHOOLS, callback_data=CB_TRAIN_SCHOOLS_OPEN),
            ],
            [InlineKeyboardButton(text=BTN_BACK_TO_PROFILE, callback_data=CB_PROFILE_OPEN)],
        ]
    )


def personal_result_menu() -> InlineKeyboardMarkup:
    # «Назад» — к тренировкам (тестер 2026-10-14: характеристики сразу после тренировки не нужны).
    from bot.constant.training import CB_TRAIN_EXTRAS_OPEN
    from bot.texts.common import BTN_BACK

    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_BACK, callback_data=CB_TRAIN_EXTRAS_OPEN)]])


def tech_list_menu(rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """(код техники, подпись) — по кнопке на технику."""
    from bot.constant.training import CB_TRAIN_EXTRAS_OPEN, CB_TRAIN_TECH_VIEW_PREFIX
    from bot.texts.training import BTN_BACK_TO_TRAINING

    kb = [[InlineKeyboardButton(text=label, callback_data=f"{CB_TRAIN_TECH_VIEW_PREFIX}{code}")] for code, label in rows]
    kb.append([InlineKeyboardButton(text=BTN_BACK_TO_TRAINING, callback_data=CB_TRAIN_EXTRAS_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def tech_menu(code: str, stage: str, *, next_level: int | None, price: int, fragments: int) -> InlineKeyboardMarkup:
    from bot.constant.training import CB_TRAIN_TECH_LEVEL_PREFIX, CB_TRAIN_TECH_OPEN, CB_TRAIN_TECH_PAY_PREFIX
    from bot.texts.training import BTN_BACK_TO_TECH_LIST, BTN_TECH_LEVEL, BTN_TECH_PAY
    from bot.utils.formatting import format_number

    kb = []
    if stage == "pay":
        kb.append([InlineKeyboardButton(text=BTN_TECH_PAY.format(price=format_number(price)), callback_data=f"{CB_TRAIN_TECH_PAY_PREFIX}{code}")])
    elif stage == "level":
        kb.append([InlineKeyboardButton(
            text=BTN_TECH_LEVEL.format(next=next_level, fragments=format_number(fragments)), callback_data=f"{CB_TRAIN_TECH_LEVEL_PREFIX}{code}",
        )])
    kb.append([InlineKeyboardButton(text=BTN_BACK_TO_TECH_LIST, callback_data=CB_TRAIN_TECH_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def schools_menu(rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """(школа, подпись) — занятие у каждого купленного учителя."""
    from bot.constant.training import CB_TRAIN_EXTRAS_OPEN, CB_TRAIN_SCHOOL_LESSON_PREFIX
    from bot.texts.training import BTN_BACK_TO_TRAINING

    kb = [[InlineKeyboardButton(text=label, callback_data=f"{CB_TRAIN_SCHOOL_LESSON_PREFIX}{school}")] for school, label in rows]
    kb.append([InlineKeyboardButton(text=BTN_BACK_TO_TRAINING, callback_data=CB_TRAIN_EXTRAS_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=kb)
