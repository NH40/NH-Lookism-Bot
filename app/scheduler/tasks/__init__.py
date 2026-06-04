# Re-exports all scheduler task functions from sub-modules
from app.scheduler.tasks.income import income_tick
from app.scheduler.tasks.ultra_instinct import ultra_instinct_tick
from app.scheduler.tasks.auction import auction_round_tick, auction_start_tick
from app.scheduler.tasks.clan import clan_war_tick, clan_auction_tick, region_war_tick
from app.scheduler.tasks.referral import referral_power_tick
from app.scheduler.tasks.notifications import _send_notifications, _get_bot
from app.scheduler.tasks.daily import daily_tick
from app.scheduler.tasks.bank import (
    bank_credit_tick,
    storage_fee_tick,
    investment_tick,
)
from app.scheduler.tasks.campaign import campaign_tick
from app.scheduler.tasks.boss import boss_tick
from app.scheduler.tasks.war_genius import war_genius_tick

__all__ = [
    "income_tick",
    "ultra_instinct_tick",
    "auction_round_tick",
    "auction_start_tick",
    "clan_war_tick",
    "clan_auction_tick",
    "region_war_tick",
    "referral_power_tick",
    "_send_notifications",
    "_get_bot",
    "daily_tick",
    "bank_credit_tick",
    "storage_fee_tick",
    "investment_tick",
    "campaign_tick",
    "boss_tick",
    "war_genius_tick",
]
