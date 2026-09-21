"""Учителя — платная разблокировка 3-го типа тренировки (тренировка статистов у учителя), изначально закрыта (хендлеры).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: «Карта» — блок «Тренировки» (упоминание учителя как будущей фичи).
"""
from __future__ import annotations

from aiogram import Router

router = Router(name="teacher")
