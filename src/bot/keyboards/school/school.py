"""Учителя статистов (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.school import SCHOOL_TEACHER_PRICE
from bot.constant.map import CB_MAP_OPEN
from bot.constant.school import CB_SCHOOL_BUY_PREFIX, CB_SCHOOL_CLAIM_PREFIX, CB_SCHOOL_MEET_PREFIX
from bot.texts.event import BTN_BACK_TO_MAP
from bot.texts.school import BTN_BUY, BTN_CLAIM, BTN_CLAIM_SHOP, BTN_MEET, SCHOOL_TEACHERS
from bot.utils.formatting import format_number


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def teacher_menu(event_id: int, school: str, *, can_meet: bool, can_claim: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_meet:
        rows.append([_btn(BTN_MEET, f"{CB_SCHOOL_MEET_PREFIX}{event_id}")])
    if can_claim:
        rows.append([_btn(BTN_CLAIM, f"{CB_SCHOOL_CLAIM_PREFIX}{school}")])
    rows.append([_btn(BTN_BACK_TO_MAP, CB_MAP_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shop_rows(teachers, claimable: list[str]) -> list[list[InlineKeyboardButton]]:
    """Кнопки раздела «Обучение» в магазине: купить учителя / позвать после задания. Занятия у
    купленных — в 🏋 Тренировках → 🏫 Школы статистов (2026-10-13)."""
    rows = [
        [_btn(BTN_BUY.format(teacher=SCHOOL_TEACHERS[t.school], price=format_number(SCHOOL_TEACHER_PRICE)), f"{CB_SCHOOL_BUY_PREFIX}{t.school}")]
        for t in teachers
        if not t.owned
    ]
    rows.extend([_btn(BTN_CLAIM_SHOP.format(teacher=SCHOOL_TEACHERS[s]), f"{CB_SCHOOL_CLAIM_PREFIX}{s}")] for s in claimable)
    return rows
