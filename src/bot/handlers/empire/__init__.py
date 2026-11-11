"""Публичное API хендлеров домена empire: экран империи (ставки), саботаж подданных, война
императоров."""
from aiogram import Router

from bot.handlers.empire.abdicate import router as _abdicate_router
from bot.handlers.empire.announcement import router as _announce_router
from bot.handlers.empire.empire import router as _rates_router
from bot.handlers.empire.events import router as _events_router
from bot.services.empire.event_push import send_finished as send_event_results  # noqa: F401
from bot.handlers.empire.sabotage import router as _sabotage_router
from bot.handlers.empire.war import router as _war_router
from bot.handlers.empire.war import send_war_reports  # noqa: F401

router = Router(name="empire")
router.include_routers(_rates_router, _announce_router, _events_router, _abdicate_router, _sabotage_router, _war_router)
