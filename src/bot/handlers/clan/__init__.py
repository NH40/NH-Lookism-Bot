"""Публичное API хендлеров домена clan — один роутер-агрегатор (главный экран, управление,
экономика, рота и война)."""
from aiogram import Router

from bot.handlers.clan.clan import render_clan
from bot.handlers.clan.clan import router as _main
from bot.handlers.clan.economy import router as _economy
from bot.handlers.clan.garrison import router as _garrison
from bot.handlers.clan.manage import router as _manage

router = Router(name="clan_root")
router.include_routers(_main, _manage, _economy, _garrison)

__all__ = ["render_clan", "router"]
