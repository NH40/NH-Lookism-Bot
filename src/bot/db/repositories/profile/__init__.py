"""Публичное API домена profile (репозиторий)."""
from bot.db.repositories.profile.profile import (  # noqa: F401
    count_districts_in_city,
    count_districts_in_country,
    count_online,
)
