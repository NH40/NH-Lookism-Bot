"""Публичное API домена arena (сервис): онлайн-бои."""
from bot.services.arena.arena import (  # noqa: F401
    ATTACK, DEFEND, PERK, PERK_REGISTRY, STATUS_DONE, STATUS_LIVE, ArenaError, act, ai_action, create, current_of, load,
    mark_seen, perks_view, register_finisher, run_auto, save, set_auto, sweep, tick,
)
from bot.services.arena.sources import energy_for, perks_for  # noqa: F401,E402
from bot.services.arena.scenarios import (  # noqa: F401,E402
    KIND_CHALLENGE, KIND_DISTRICT, KIND_LIBERATION, KIND_THRONE, set_notifier, set_session_factory, start_challenge,
    start_district, start_throne,
)
from bot.services.arena.scenarios_pve import (  # noqa: F401,E402
    KIND_BOSS, KIND_CITY, KIND_RAID, KIND_TOM, KIND_WAR, start_boss, start_city, start_raid, start_tom, start_war,
)
