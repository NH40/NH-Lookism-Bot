"""Публичное API домена arena (сервис): онлайн-бои."""
from bot.services.arena.arena import (  # noqa: F401
    ATTACK, DEFEND, PERK, PERK_REGISTRY, STATUS_DONE, STATUS_LIVE, ArenaError, act, ai_action, create, current_of, load,
    perks_view, register_finisher, run_auto, save, set_auto, sweep, tick,
)
from bot.services.arena.sources import energy_for, perks_for  # noqa: F401,E402
from bot.services.arena.scenarios import KIND_DISTRICT, set_session_factory, start_district  # noqa: F401,E402
