"""Публичное API домена arena (сервис): онлайн-бои."""
from bot.services.arena.arena import (  # noqa: F401
    ATTACK, DEFEND, PERK, PERK_REGISTRY, STATUS_DONE, STATUS_LIVE, ArenaError, act, ai_action, create, current_of, load,
    perks_view, register_finisher, run_auto, set_auto, tick,
)
