"""Публичное API домена extra (репозиторий)."""
from bot.db.repositories.extra.extra import (  # noqa: F401
    add_to_stack,
    get_stack_for_update,
    list_stacks,
    total_quantity,
)
