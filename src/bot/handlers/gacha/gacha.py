"""Крутки за тикеты — получение уникального персонажа через вербовку (хендлеры).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: «Карта» — блок «Вербовка» + «Уникальные персонажи».
"""
from __future__ import annotations

from aiogram import Router

router = Router(name="gacha")
