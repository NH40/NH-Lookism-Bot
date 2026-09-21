"""Каталог/коллекция уникальных персонажей — те же карточки (assets/), что и раньше, но перки теперь привязаны к позиции в банде, не к UBP/тиру (хендлеры).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: «Уникальные персонажи».
"""
from __future__ import annotations

from aiogram import Router

router = Router(name="card")
