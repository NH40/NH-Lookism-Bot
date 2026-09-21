"""Экран «Карта» — выбор страны -> города -> районов, счётчики игроков/кругов/банд, меню Карта/Банда/Вербовка/Бизнес, экран войн кулаков за страну на фазе «Кулак» (хендлеры).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: «Карта» (весь блок) + «Фазы» (война кулаков за страну).
"""
from __future__ import annotations

from aiogram import Router

router = Router(name="map")
