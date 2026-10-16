"""Публичное API домена bloodline (репозиторий)."""
from bot.db.repositories.bloodline.bloodline import (  # noqa: F401
    choose,
    get_state,
    level_up,
    raise_stats_to,
    set_level_if_zero,
)
