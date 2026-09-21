"""Рейды — 3 фракции (Кулак Гапрена / Синдикат Ямадзаки / DG Company), именные боссы с уникальной механикой боя на каждого (хендлеры).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: «Развитие» — блок «Рейды» (самый детальный раздел про боссов).
"""
from __future__ import annotations

from aiogram import Router

router = Router(name="raid")
