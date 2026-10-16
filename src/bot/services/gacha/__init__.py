"""Публичное API домена gacha (сервис)."""
from bot.services.gacha.gacha import NoTicketsError, RollBusyError, RollResult, pick_card, roll  # noqa: F401
