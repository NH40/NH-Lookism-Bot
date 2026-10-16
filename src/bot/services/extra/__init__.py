"""Публичное API домена extra (сервис)."""
from bot.services.extra.extra import (  # noqa: F401
    ArmyStats,
    CampStats,
    InvalidCampMoveError,
    Squad,
    get_army_stats,
    get_squad,
    list_army_squads,
    list_squads,
    move_between_camps,
    move_squad,
    recruit_into_stack,
)
