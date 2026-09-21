"""Точка сборки всех роутеров бота — единый get_routers() (см. main.py).

Порядок важен:
  - start/common — первыми, самые частые апдейты;
  - admin — роутер закрыт IsAdminFilter (см. filters/admin.py), вешать фильтр в
    handlers/admin/admin.py на сам router, как только домен наполнится;
  - fallback (catch-all без фильтров) — строго ПОСЛЕДНИМ, иначе перехватит апдейты,
    предназначенные другим доменам (см. CLAUDE.md UAP, "Антифлуд и fallback").
"""
from __future__ import annotations

from aiogram import Router

from bot.handlers.start import router as start_router
from bot.handlers.common import router as common_router
from bot.handlers.profile import router as profile_router
from bot.handlers.admin import router as admin_router
from bot.handlers.settings import router as settings_router
from bot.handlers.guide import router as guide_router
from bot.handlers.referral import router as referral_router
from bot.handlers.promo import router as promo_router
from bot.handlers.donate import router as donate_router
from bot.handlers.payment import router as payment_router
from bot.handlers.map import router as map_router
from bot.handlers.district import router as district_router
from bot.handlers.gang import router as gang_router
from bot.handlers.recruit import router as recruit_router
from bot.handlers.business import router as business_router
from bot.handlers.training import router as training_router
from bot.handlers.teacher import router as teacher_router
from bot.handlers.mastery import router as mastery_router
from bot.handlers.card import router as card_router
from bot.handlers.gacha import router as gacha_router
from bot.handlers.collection import router as collection_router
from bot.handlers.raid import router as raid_router
from bot.handlers.campaign import router as campaign_router
from bot.handlers.boss import router as boss_router
from bot.handlers.ultra_instinct import router as ultra_instinct_router
from bot.handlers.unique_technique import router as unique_technique_router
from bot.handlers.unique_path import router as unique_path_router
from bot.handlers.bloodline import router as bloodline_router
from bot.handlers.genius import router as genius_router
from bot.handlers.awakening import router as awakening_router
from bot.handlers.clan import router as clan_router
from bot.handlers.quest import router as quest_router
from bot.handlers.shop import router as shop_router
from bot.handlers.fallback import router as fallback_router


def get_routers() -> list[Router]:
    return [
        start_router,
        common_router,
        profile_router,
        admin_router,
        settings_router,
        guide_router,
        referral_router,
        promo_router,
        donate_router,
        payment_router,
        map_router,
        district_router,
        gang_router,
        recruit_router,
        business_router,
        training_router,
        teacher_router,
        mastery_router,
        card_router,
        gacha_router,
        collection_router,
        raid_router,
        campaign_router,
        boss_router,
        ultra_instinct_router,
        unique_technique_router,
        unique_path_router,
        bloodline_router,
        genius_router,
        awakening_router,
        clan_router,
        quest_router,
        shop_router,
        fallback_router,
    ]
