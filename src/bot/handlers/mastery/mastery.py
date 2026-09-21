"""Мастерство — сила/скорость/выносливость/техника, 3 ступени (Стена -> Трансцендентность -> Мастерство) (хендлеры).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: «Профиль» — блок «пробуждения мастерства».
"""
from __future__ import annotations

from aiogram import Router

router = Router(name="mastery")
