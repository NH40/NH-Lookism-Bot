from aiogram import Router
from app.handlers.clan import main, invite, treasury, shop, auction, war, exchange, edit

router = Router()
router.include_router(main.router)
router.include_router(invite.router)
router.include_router(treasury.router)
router.include_router(shop.router)
router.include_router(auction.router)
router.include_router(war.router)
router.include_router(exchange.router)
router.include_router(edit.router)