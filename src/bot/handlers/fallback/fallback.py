"""Catch-all для нераспознанных апдейтов (хендлеры).

TODO: портировать из LookismBattlePlanet 1.0 — новый — аналог bot/handlers/fallback в UAP.
"""
from __future__ import annotations

from aiogram import Router

router = Router(name="fallback")
