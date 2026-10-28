"""Публичное API домена characteristic (репозиторий)."""
from bot.db.repositories.characteristic.characteristic import (  # noqa: F401
    CombatRow,
    StatsRow,
    add_points,
    award_potential_points,
    get_combat_row,
    get_stats,
    get_strength,
    invest,
    set_potential_if_missing,
    upgrade_potential,
)
