"""Просмотр коллекции уникальных персонажей (только чтение) (хендлеры).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: «Уникальные персонажи».
"""
from __future__ import annotations

from aiogram import Router

router = Router(name="collection")
