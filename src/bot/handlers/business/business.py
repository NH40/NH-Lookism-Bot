"""Бизнесы на районе — кофе/зал/магазин/нелегальный рынок/парламент, прокачка уровень/вместимость/скидка (хендлеры).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: «Карта» — блок «Бизнес» (в конце сообщения про сражения).
"""
from __future__ import annotations

from aiogram import Router

router = Router(name="business")
