"""Школы учителей статистов (константы). Пользователь 2026-10-03: учителя статистов
встречаются на карте и выводят статистов в свои школы — Хансу (ловкость), Элита (скорость),
Бэкхо (техника), Том Ли (сила). Код школы — часть ключа стопки (`extras.school`)."""
from __future__ import annotations

SCHOOL_NONE = ""
SCHOOL_STRENGTH = "str"  # Том Ли
SCHOOL_AGILITY = "agi"  # Хансу
SCHOOL_SPEED = "spd"  # Элита
SCHOOL_TECHNIQUE = "tec"  # Бэкхо
SCHOOLS: tuple[str, ...] = (SCHOOL_STRENGTH, SCHOOL_AGILITY, SCHOOL_SPEED, SCHOOL_TECHNIQUE)

CB_SCHOOL_TRAIN_PREFIX = "school:train:"
"""f"{CB_SCHOOL_TRAIN_PREFIX}{school}" — занятие у учителя."""
CB_SCHOOL_BUY_PREFIX = "school:buy:"
"""f"{CB_SCHOOL_BUY_PREFIX}{school}" — купить учителя в магазине."""
CB_SCHOOL_CLAIM_PREFIX = "school:claim:"
"""f"{CB_SCHOOL_CLAIM_PREFIX}{school}" — выполненный квест учителя → он в магазине."""
CB_SCHOOL_OPEN = "school:open"
CB_SCHOOL_MEET_PREFIX = "school:meet:"
"""f"{CB_SCHOOL_MEET_PREFIX}{event_id}" — взять задание у учителя статистов на карте."""
LOCK_ACTION_SCHOOL = "school"
