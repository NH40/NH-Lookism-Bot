"""Походы — тип события на карте (хендлеры).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: «Развитие» — упомянут в списке из 4 событий, детали не описаны.
"""
from __future__ import annotations

from aiogram import Router

router = Router(name="campaign")
