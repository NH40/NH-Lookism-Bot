from aiogram import Router

from app.handlers.raid.menu import router as menu_router
from app.handlers.raid.boss import router as boss_router
from app.handlers.raid.attack import router as attack_router
from app.handlers.raid.rewards import router as rewards_router

router = Router()
router.include_router(menu_router)
router.include_router(boss_router)
router.include_router(attack_router)
router.include_router(rewards_router)

__all__ = ["router"]
