"""Район — список районов города, захват (PvP/PvE), кнопки Сражения/Шпионаж/Разведка, вызов на бой с таймером принятия (1 час, зависит от скорости) (хендлеры).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: «Карта» — блок про район/сражения/КД на сражения по фазам.
"""
from __future__ import annotations

from aiogram import Router

router = Router(name="district")
