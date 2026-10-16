"""Публичное API домена settings (сервис)."""
from bot.services.settings.settings import (  # noqa: F401
    UnknownCategoryError,
    is_muted,
    muted_categories,
    notify_player,
    set_all,
    toggle,
)
