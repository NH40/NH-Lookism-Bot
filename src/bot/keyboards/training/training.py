"""Тренировки — личная (очки развития, КД 1 час) и тренировка статистов (3 этапа: прокачка мощи / пробуждение звёзд / повышение ранга) (клавиатуры)."""
from __future__ import annotations

from bot.constant.profile import CB_PROFILE_OPEN
from bot.texts.common import BTN_BACK_TO_PROFILE

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.training import (
    CB_RANKS_LOCK_PREFIX,
    CB_RANKS_OPEN,
    CB_RANKS_PROMOTE_PREFIX,
    CB_TRAIN_EXTRAS_OPEN,
    CB_TRAIN_EXTRAS_RUN,
    CB_TRAIN_PERSONAL,
)
from bot.texts.training import BTN_BACK_TO_TRAINING, BTN_PERSONAL_TRAINING, BTN_RANK_LOCK, BTN_RANK_PROMOTE, BTN_RANKS
from bot.utils.formatting import format_number

BTN_TRAIN_EXTRAS_RUN = "🏋️ Тренировать статистов"


from bot.constant.training import CB_TRAIN_SCHOOLS_OPEN, CB_TRAIN_TECH_OPEN  # noqa: E402
from bot.texts.training import BTN_SCHOOLS, BTN_TECH_TRAINING  # noqa: E402

def train_menu(*, ranks: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=BTN_PERSONAL_TRAINING, callback_data=CB_TRAIN_PERSONAL)],
        [InlineKeyboardButton(text=BTN_TRAIN_EXTRAS_RUN, callback_data=CB_TRAIN_EXTRAS_RUN)],
        [
            InlineKeyboardButton(text=BTN_TECH_TRAINING, callback_data=CB_TRAIN_TECH_OPEN),
            InlineKeyboardButton(text=BTN_SCHOOLS, callback_data=CB_TRAIN_SCHOOLS_OPEN),
        ],
    ]
    if ranks:  # родословная Самдака
        rows.append([InlineKeyboardButton(text=BTN_RANKS, callback_data=CB_RANKS_OPEN)])
    rows.append([InlineKeyboardButton(text=BTN_BACK_TO_PROFILE, callback_data=CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ranks_menu(rows) -> InlineKeyboardMarkup:
    """Строка на ранг: запрет перехода и перевод вручную тех, кто дошёл до обычного капа."""
    keyboard = []
    for r in rows:
        row = [InlineKeyboardButton(
            text=BTN_RANK_LOCK.format(mark="🔒" if r.locked else "🔓", rank=r.rank), callback_data=f"{CB_RANKS_LOCK_PREFIX}{r.rank}"
        )]
        if r.ready and r.next_rank:
            row.append(InlineKeyboardButton(
                text=BTN_RANK_PROMOTE.format(next_rank=r.next_rank, count=format_number(r.ready)),
                callback_data=f"{CB_RANKS_PROMOTE_PREFIX}{r.rank}",
            ))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text=BTN_BACK_TO_TRAINING, callback_data=CB_TRAIN_EXTRAS_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


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
    elif stage == "quest":
        from bot.constant.training import CB_TRAIN_TECH_PLAY_PREFIX
        from bot.texts.minigame import BTN_TECH_PLAY

        kb.append([InlineKeyboardButton(text=BTN_TECH_PLAY, callback_data=f"{CB_TRAIN_TECH_PLAY_PREFIX}{code}")])
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
