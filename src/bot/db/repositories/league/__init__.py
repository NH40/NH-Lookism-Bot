"""Публичное API домена league (репозиторий)."""
from bot.db.repositories.league.league import (  # noqa: F401
    all_scores,
    clan_of_all,
    income_counts,
    move_to_league_maps,
    set_leagues,
    set_scores,
    strip_territory,
)
