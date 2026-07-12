from aiogram import Router

from app.handlers.market.menu import router as menu_router
from app.handlers.market.sell import router as sell_router
from app.handlers.market.buy import router as buy_router
from app.handlers.market.my_lots import router as my_lots_router
from app.handlers.market.auction import router as auction_router

router = Router()
router.include_router(menu_router)
router.include_router(sell_router)
router.include_router(buy_router)
router.include_router(my_lots_router)
router.include_router(auction_router)

__all__ = ["router"]
