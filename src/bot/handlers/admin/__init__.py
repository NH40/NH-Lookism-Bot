"""Публичное API хендлеров домена admin: корневой роутер с фильтром прав.

`IsAdminFilter` — на корневом роутере: фильтры родителя действуют на все вложенные роутеры
разделов. Не-админам админка молча не отвечает (не палить её существование). Права на
конкретный раздел — `handlers/admin/common.guard` внутри каждого раздела.
"""
from aiogram import Router

from bot.filters.admin import IsAdminFilter
from bot.handlers.admin.admin import router as _admin
from bot.handlers.admin.players import router as _players
from bot.handlers.admin.give import router as _give
from bot.handlers.admin.dev import router as _dev
from bot.handlers.admin.punish import router as _punish
from bot.handlers.admin.mass import router as _mass
from bot.handlers.admin.promo import router as _promo
from bot.handlers.admin.stats import router as _stats
from bot.handlers.admin.logs import router as _logs
from bot.handlers.admin.world import router as _world
from bot.handlers.admin.events import router as _events
from bot.handlers.admin.clans import router as _clans
from bot.handlers.admin.season import router as _season
from bot.handlers.admin.roles import router as _roles
from bot.handlers.admin.patch import router as _patch
from bot.handlers.admin.live_config import router as _live_config
from bot.handlers.admin.referral import router as _referral
from bot.handlers.admin.quests import router as _quests
from bot.handlers.admin.statists import router as _statists

router = Router(name="admin_root")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())
router.include_routers(_admin, _players, _give, _dev, _punish, _mass, _promo, _stats, _logs, _world, _events, _clans, _season, _roles, _patch, _live_config, _referral, _quests, _statists)
