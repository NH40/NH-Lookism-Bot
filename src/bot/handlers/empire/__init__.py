"""Публичное API хендлеров домена empire: экран империи (ставки), саботаж подданных, война
императоров."""
from aiogram import Router

from bot.handlers.empire.empire import router as _rates_router
from bot.handlers.empire.sabotage import router as _sabotage_router
from bot.handlers.empire.war import router as _war_router
from bot.handlers.empire.war import send_war_reports  # noqa: F401

router = Router(name="empire")
router.include_routers(_rates_router, _sabotage_router, _war_router)
