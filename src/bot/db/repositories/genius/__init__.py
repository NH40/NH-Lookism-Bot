"""Публичное API домена genius (репозиторий)."""
from bot.db.repositories.genius.genius import (  # noqa: F401
    add,
    bump_level,
    get_state,
    list_owned,
    set_active,
    set_active_if_missing,
    spend_fragments,
)
