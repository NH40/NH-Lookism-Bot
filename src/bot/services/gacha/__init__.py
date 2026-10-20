"""Публичное API домена gacha (сервис)."""
from bot.services.gacha.gacha import (  # noqa: F401
    MassRollResult,
    NoTicketsError,
    RollBusyError,
    RollResult,
    pick_card,
    roll,
    roll_many,
)
