from aiogram import Router

from .menu import router as _menu_router

router = Router()
router.include_router(_menu_router)

# Re-export shared helper for callers that import it directly
from ._common import _show_business_main  # noqa: F401
