"""Публичное API домена arena (сервис): онлайн-бои."""
from bot.services.arena.arena import (  # noqa: F401
    ATTACK, DEFEND, PERK, PERK_REGISTRY, STATUS_DONE, STATUS_LIVE, ArenaError, act, actions_view, ai_action, create, current_of,
    finish_now, load,
    foe_intel, mark_seen, perks_view, register_finisher, run_auto, save, set_auto, sweep, tick,
)
from bot.services.arena.sources import (  # noqa: F401,E402
    LoadoutFullError, energy_for, loadout, perks_for, set_auto_default, toggle_loadout,
)
from bot.services.arena.scenarios import (  # noqa: F401,E402
    KIND_CHALLENGE, KIND_CLAN_WAR, KIND_DISTRICT, KIND_LIBERATION, KIND_THRONE, set_notifier, set_session_factory,
    start_challenge, start_clan_war, start_district, start_throne,
)
from bot.services.arena.scenarios_pve import (  # noqa: F401,E402
    KIND_BOSS, KIND_CITY, KIND_RAID, KIND_TOM, KIND_TUTORIAL, KIND_WAR, start_boss, start_city, start_raid, start_tom,
    start_tutorial, start_war,
)
