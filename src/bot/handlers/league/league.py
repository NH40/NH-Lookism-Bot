"""Лиги: пуши о повышении и фоновый проход. Экранов нет: новая страна выбирается в обычном меню выбора страны."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.league import LEAGUE_INCOME_STEP, LEAGUE_POWER_STEP, LEAGUE_SWEEP_TICK_SECONDS, LEAGUES
from bot.keyboards.start import country_menu
from bot.services.country import closed_entries
from bot.services.league import daily_sweep, sweep_due
from bot.texts.league import PROMOTED
from bot.utils.notify import notify

log = logging.getLogger(__name__)
_PUSHES_PER_SECOND = 20


async def send_promotions(bot: Bot, session_factory: async_sessionmaker[AsyncSession], promoted: list[tuple[int, int]],
                          *, demoted: bool = False) -> None:
    from bot.config.league import LEAGUE_INACTIVE_DAYS
    from bot.texts.league import DEMOTED

    async with session_factory() as session:
        closed = await closed_entries(session)
    for i, (user_id, league) in enumerate(promoted, 1):
        text = DEMOTED.format(name=LEAGUES[league].name, days=LEAGUE_INACTIVE_DAYS) if demoted else PROMOTED.format(name=LEAGUES[league].name, income=round(LEAGUE_INCOME_STEP * league * 100), power=round(LEAGUE_POWER_STEP * league * 100))
        await notify(bot, user_id, text, reply_markup=country_menu(closed, league))
        if i % _PUSHES_PER_SECOND == 0:
            await asyncio.sleep(1)


REDISTRIBUTE_REQUEST_KEY = "league:redistribute:request"  # Mini App просит бота пересчитать лиги (значение — id админа)
_REQUEST_POLL_SECONDS = 10


async def league_loop(bot: Bot, session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> None:
    while True:
        try:
            if await sweep_due(redis):
                promoted, demoted = await daily_sweep(session_factory)
                log.info("League sweep: promoted %d, demoted %d", len(promoted), len(demoted))
                await send_promotions(bot, session_factory, promoted)
                await send_promotions(bot, session_factory, demoted, demoted=True)
        except Exception:
            log.exception("League sweep failed")
        # Пересчёт из Mini App идёт здесь, в процессе бота: пересчёт мощи всем тяжёлый, у API лимит памяти меньше.
        for _ in range(max(1, LEAGUE_SWEEP_TICK_SECONDS // _REQUEST_POLL_SECONDS)):
            try:
                admin = await redis.getdel(REDISTRIBUTE_REQUEST_KEY)
                if admin:
                    from bot.handlers.admin.world import run_league_recalc

                    admin_id = int(admin)
                    await run_league_recalc(bot, session_factory, redis, admin_id, admin_id)
            except Exception:
                log.exception("League redistribute request failed")
            await asyncio.sleep(_REQUEST_POLL_SECONDS)


async def send_moved(bot: Bot, moved: list[tuple[int, int, int]]) -> None:
    """Пуш переехавшим при пересчёте лиг из админки: территория уехала с ними, страну выбирать не нужно."""
    from bot.texts.league import MOVED

    for i, (user_id, _, league) in enumerate(moved, 1):
        text = MOVED.format(name=LEAGUES[league].name, income=round(LEAGUE_INCOME_STEP * league * 100), power=round(LEAGUE_POWER_STEP * league * 100))
        await notify(bot, user_id, text)
        if i % _PUSHES_PER_SECOND == 0:
            await asyncio.sleep(1)


def axes_lines(stats) -> str:
    """Лиги по силе для админки: выключатель, пороги и разброс мощи/СР по нынешним лигам (подбор порогов)."""
    from bot.config import league as cfg
    from bot.services.combat.explain import compact

    on = bool(cfg.league.LEAGUE_STATIC_AXES)
    lines = [
        f"⚖️ <b>Лиги по силе</b>: {'включены' if on else 'выключены (работает прежний счёт)'}",
        "Пороги мощи: " + " / ".join(compact(x) for x in cfg.league.LEAGUE_POWER_THRESHOLDS),
        "Пороги силы развития: " + " / ".join(str(x) for x in cfg.league.LEAGUE_DEV_THRESHOLDS),
        "Сейчас (активные за 3 дня, 10% · медиана · 90%):",
    ]
    for s in stats:
        p, d = s.power, s.dev
        lines.append(f"• {LEAGUES[s.league].name} ({s.players}): мощь {compact(p[0])} · {compact(p[1])} · {compact(p[2])}; "
                     f"СР {d[0]} · {d[1]} · {d[2]}")
    lines.append("Пороги и выключатель — «Настройки игры» → лиги. Предпросмотр ниже считает по ним.")
    return "\n".join(lines)


def plan_lines(plan) -> tuple[str, str]:
    """Тексты «игроков по лигам» и «переезды» для админки (бот и Mini App)."""
    counts = "\n".join(f"• {LEAGUES[lg].name}: <b>{n}</b>" for lg, n in plan.counts.items())
    moves = "\n".join(f"• {LEAGUES[a].name} → {LEAGUES[b].name}: {n}" for (a, b), n in plan.moves.items()) or "• никто"
    return counts, moves
