"""Публичное API домена referral (репозиторий)."""
from bot.db.repositories.referral.referral import (  # noqa: F401
    add,
    add_visit,
    campaign_stats,
    delete_link,
    get,
    get_by_code,
    list_with_counts,
)
