"""Публичное API домена unique_technique (репозиторий)."""
from bot.db.repositories.unique_technique.unique_technique import (  # noqa: F401
    add,
    bump_level,
    delete_all,
    get_state,
    list_owned,
    set_active,
    set_active_if_missing,
    spend_fragments,
)
