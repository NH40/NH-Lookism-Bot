from aiogram import Router
from app.handlers.bank.casino.menu import router as menu_router
from app.handlers.bank.casino.slots import router as slots_router
from app.handlers.bank.casino.blackjack import router as blackjack_router
from app.handlers.bank.casino.rating import router as rating_router
from app.handlers.bank.casino.poker import router as poker_router

router = Router()
router.include_router(menu_router)
router.include_router(slots_router)
router.include_router(blackjack_router)
router.include_router(rating_router)
router.include_router(poker_router)

__all__ = ["router"]
