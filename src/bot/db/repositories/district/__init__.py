"""Публичное API домена district (репозиторий)."""
from bot.db.repositories.district import challenge  # noqa: F401
from bot.db.repositories.district.district import (  # noqa: F401
    CityStatsRow,
    DistrictRow,
    OwnerGroupRow,
    capture_all_bots_in_city,
    capture_from_bots,
    city_owner_groups,
    count_owned,
    count_owned_in_city,
    country_city_stats,
    get_row,
    list_by_city,
    seed_districts,
    transfer_all_in_city,
    transfer_owner,
)
