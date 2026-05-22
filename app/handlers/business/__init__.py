from aiogram import Router

from .menu import router as _menu_router
from .buildings import router as _buildings_router
from .build import router as _build_router

router = Router()
router.include_router(_menu_router)
router.include_router(_buildings_router)
router.include_router(_build_router)

# Re-export shared helper for callers that import it directly
from ._common import _show_business_main  # noqa: F401
