from aiogram import Router

from .menu import router as _menu_router
from .top import router as _top_router
from .promo import router as _promo_router
from .admin_cmd import router as _admin_router
from .slava import router as _slava_router

router = Router()
router.include_router(_menu_router)
router.include_router(_top_router)
router.include_router(_promo_router)
router.include_router(_admin_router)
router.include_router(_slava_router)

# Re-export shared helpers for any code that imports from this package
from ._common import (  # noqa: F401
    CommonFSM,
    _redis,
    _get_top_cached,
    _get_players_page_cached,
    _phase_emoji,
    _main_menu_text,
    PAGE_SIZE,
)
