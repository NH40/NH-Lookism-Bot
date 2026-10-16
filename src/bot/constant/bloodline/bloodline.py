"""Родословная (константы). Дизайн — `docs/design/development_systems.md`."""
from __future__ import annotations

# Коды 10 родословных (пользователь 2026-10-02) — хранятся в `users.bloodline`.
BLOODLINE_ELITE = "elite"
BLOODLINE_MUJIN = "mujin"
BLOODLINE_JINYEONG = "jinyeong"
BLOODLINE_GAPRYONG = "gapryong"
BLOODLINE_YAMAZAKI = "yamazaki"
BLOODLINE_SAMDAK = "samdak"
BLOODLINE_SOPHIA = "sophia"
BLOODLINE_KURODA = "kuroda"
BLOODLINE_JINCHEOL = "jincheol"
BLOODLINE_HANSU = "hansu"
BLOODLINES: tuple[str, ...] = (
    BLOODLINE_ELITE,
    BLOODLINE_MUJIN,
    BLOODLINE_JINYEONG,
    BLOODLINE_GAPRYONG,
    BLOODLINE_YAMAZAKI,
    BLOODLINE_SAMDAK,
    BLOODLINE_SOPHIA,
    BLOODLINE_KURODA,
    BLOODLINE_JINCHEOL,
    BLOODLINE_HANSU,
)

CB_BLOODLINE_LIST = "bloodline:list"
CB_BLOODLINE_VIEW_PREFIX = "bloodline:view:"
"""f"{CB_BLOODLINE_VIEW_PREFIX}{code}" — описание перед выбором."""
CB_BLOODLINE_PICK_PREFIX = "bloodline:pick:"
CB_BLOODLINE_SCREEN = "bloodline:screen"
CB_BLOODLINE_LEVEL_UP = "bloodline:up"
"""f"{CB_BLOODLINE_PICK_PREFIX}{code}" — выбрать навсегда."""

CB_BLOODLINE2_CHOOSE_PREFIX = "bloodline:pick2:"
"""f"{CB_BLOODLINE2_CHOOSE_PREFIX}{code}" — выбрать вторую родословную."""
CB_BLOODLINE2_LIST = "bloodline:list2"
CB_BLOODLINE2_LEVEL_UP = "bloodline:up2"
CB_BLOODLINE2_SCREEN = "bloodline:screen2"  # уровни второй родословной (второе тело)
