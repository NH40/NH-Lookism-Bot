from aiogram import Router
from app.handlers.bosses.menu import router as menu_router

router = Router()
router.include_router(menu_router)

__all__ = ["router"]
