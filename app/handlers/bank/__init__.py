from aiogram import Router
from app.handlers.bank.menu import router as menu_router
from app.handlers.bank.credits import router as credits_router
from app.handlers.bank.casino import router as casino_router
from app.handlers.bank.storage import router as storage_router
from app.handlers.bank.investments import router as investments_router

router = Router()
router.include_router(menu_router)
router.include_router(credits_router)
router.include_router(casino_router)
router.include_router(storage_router)
router.include_router(investments_router)

__all__ = ["router"]
