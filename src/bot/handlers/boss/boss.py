"""Боссы и мировые боссы — типы событий на карте (хендлеры).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: «Развитие» — упомянуты в списке из 4 событий, детали не описаны.
"""
from __future__ import annotations

from aiogram import Router

router = Router(name="boss")
