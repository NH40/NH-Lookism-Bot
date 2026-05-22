from aiogram import Router

from app.handlers.skills.menu import router as menu_router
from app.handlers.skills.mastery import router as mastery_router
from app.handlers.skills.path import router as path_router
from app.handlers.skills.shop import router as shop_router

router = Router()
router.include_router(menu_router)
router.include_router(mastery_router)
router.include_router(path_router)
router.include_router(shop_router)

__all__ = ["router"]
