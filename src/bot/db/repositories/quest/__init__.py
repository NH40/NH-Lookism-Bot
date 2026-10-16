"""Публичное API домена quest (репозиторий)."""
from bot.db.repositories.quest.quest import (  # noqa: F401
    add_completed,
    advance,
    codes_since,
    delete_slots,
    insert,
    list_day,
    lock_state,
    purge_before,
    state_day,
)
