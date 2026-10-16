"""Публичное API домена promo (репозиторий)."""
from bot.db.repositories.promo.promo import (  # noqa: F401
    add,
    delete_promo,
    get,
    get_by_code,
    increment_used,
    insert_redemption,
    list_recent,
    set_active,
)
