"""Публичное API домена phase (сервис)."""
from bot.services.phase.phase import (  # noqa: F401
    Promotion,
    can_conquer_cities,
    check_promotion,
    crown,
    crown_with_autobuild,
    demote_to_gang,
    is_city_conqueror,
    is_emperor,
)
