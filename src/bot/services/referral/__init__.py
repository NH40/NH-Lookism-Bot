"""Публичное API домена referral (сервис)."""
from bot.services.referral.referral import (  # noqa: F401
    create_campaign,
    deep_link,
    delete_campaign,
    get_campaign,
    list_campaigns,
    record_visit,
    stats,
)
