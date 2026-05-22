from aiogram import Router

from app.handlers.admin.main import router as main_router
from app.handlers.admin.users import router as users_router
from app.handlers.admin.titles import router as titles_router
from app.handlers.admin.resources import router as resources_router
from app.handlers.admin.fragments import router as fragments_router
from app.handlers.admin.give_items import router as give_items_router
from app.handlers.admin.broadcast import router as broadcast_router
from app.handlers.admin.promo import router as promo_router
from app.handlers.admin.patch import router as patch_router
from app.handlers.admin.clan_donat import router as clan_donat_router

router = Router()
router.include_router(main_router)
router.include_router(users_router)
router.include_router(titles_router)
router.include_router(resources_router)
router.include_router(fragments_router)
router.include_router(give_items_router)
router.include_router(broadcast_router)
router.include_router(promo_router)
router.include_router(patch_router)
router.include_router(clan_donat_router)

__all__ = ["router"]
