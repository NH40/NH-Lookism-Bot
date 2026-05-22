"""Пакет хэндлеров карточек v1.2.0."""
from aiogram import Router
from app.handlers.cards import menu, gacha, collection, fusion, my_deck, duel

router = Router()
router.include_router(menu.router)
router.include_router(gacha.router)
router.include_router(collection.router)
router.include_router(fusion.router)
router.include_router(my_deck.router)
router.include_router(duel.router)

__all__ = ["router"]
