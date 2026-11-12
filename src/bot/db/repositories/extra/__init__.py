"""Публичное API домена extra (репозиторий)."""
from bot.db.repositories.extra.extra import (  # noqa: F401
    StackKey,
    add_to_stack,
    add_to_stacks,
    get_stack_for_update,
    list_stacks,
    stack_key,
    total_quantity,
)
