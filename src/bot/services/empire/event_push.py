"""Ивенты императора: пуш подданным о запуске и итоги (рассылка — общая для бота и Mini App)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.empire import (
    EMPIRE_ANNOUNCE_BATCH_PAUSE_SECONDS,
    EMPIRE_ANNOUNCE_BATCH_SIZE,
    EMPIRE_DAILY_GIFT_MAX_DAYS,
    EMPIRE_DRILL_CD_PERCENT,
    EMPIRE_EVENT_CLAIM_HOURS,
    EMPIRE_EVENT_MIN_FUND,
    EMPIRE_FEAST_INCOME_PERCENT,
    EMPIRE_GIFT_COINS_PER_POWER,
    EMPIRE_TOURNAMENT_HOURS,
)
from bot.constant.empire import EVENT_COINS, EVENT_DAILY, EVENT_STATISTS
from bot.constant.settings import NOTIFY_EMPEROR
from bot.keyboards.empire.events import push_menu
from bot.services.empire import events as ev
from bot.services.settings import notify_player
from bot.texts.empire import events as t
from bot.utils.formatting import esc, format_countdown, format_number

log = logging.getLogger(__name__)


def about(kind: str) -> str:
    return t.ABOUT[kind].format(
        claim_hours=EMPIRE_EVENT_CLAIM_HOURS, per_power=EMPIRE_GIFT_COINS_PER_POWER, feast=EMPIRE_FEAST_INCOME_PERCENT,
        drill=EMPIRE_DRILL_CD_PERCENT, tour_hours=EMPIRE_TOURNAMENT_HOURS, max_days=EMPIRE_DAILY_GIFT_MAX_DAYS,
    )


def prompt(kind: str, hours: int = 0) -> str:
    return t.PROMPTS[kind].format(hours=hours, min_fund=format_number(EMPIRE_EVENT_MIN_FUND), max_days=EMPIRE_DAILY_GIFT_MAX_DAYS)


def error_text(exc: Exception, kind: str, hours: int) -> str:
    if isinstance(exc, ev.NotEmperorError):
        return t.NOT_EMPEROR_ALERT
    if isinstance(exc, ev.EventActiveError):
        return t.ACTIVE_ALERT
    if isinstance(exc, ev.EventCooldownError):
        return t.COOLDOWN_ALERT.format(left=format_countdown(exc.seconds))
    if isinstance(exc, ev.NotEnoughCoinsError):
        return t.NOT_ENOUGH_ALERT.format(cost=format_number(exc.cost))
    if isinstance(exc, ev.NoSubjectsError):
        return t.NO_SUBJECTS_ALERT
    return t.BAD_INPUT.format(prompt=prompt(kind, hours)) if kind in t.PROMPTS else t.BAD_INPUT.format(prompt="")


def details(kind: str, params: dict, *, slots: int = 0, hours: int = 0) -> str:
    return t.DETAILS[kind].format(
        per=format_number(int(params.get("per", 0))), slots=slots, rank=params.get("rank", ""),
        hours=hours or params.get("hours", EMPIRE_EVENT_CLAIM_HOURS), percent=params.get("percent", 0),
        prize=format_number(int(params.get("prize", 0))), days=params.get("days", 0),
    )


async def deliver_started(bot: Bot, session_factory: async_sessionmaker[AsyncSession], started: ev.Started) -> None:
    """Пуш подданным о запуске (выключившие сообщения императора не получают). Своя сессия:
    хендлер к этому моменту завершён."""
    try:
        async with session_factory() as session:
            recipients = await ev.push_recipients(session, started.emperor_id)
            from bot.db.repositories.user import get_by_id

            emperor = await get_by_id(session, started.emperor_id)
            slots = started.params.get("slots", 0)
            if started.kind in (EVENT_COINS, EVENT_STATISTS):
                from sqlalchemy import text as sql

                slots = await session.scalar(sql("SELECT slots FROM empire_events WHERE id = :e"), {"e": started.event_id}) or 0
        name = (emperor.display_name or emperor.username or "Император") if emperor else "Император"
        hours = int((started.ends_at - datetime.now(timezone.utc)).total_seconds() // 3600 + 0.5)
        body = t.PUSH_STARTED.format(
            emperor=esc(name), title=t.TITLES[started.kind], details=details(started.kind, started.params, slots=slots, hours=hours),
        )
        markup = push_menu(started.event_id if started.kind in (EVENT_COINS, EVENT_STATISTS, EVENT_DAILY) else None)
        for i, user_id in enumerate(recipients, 1):
            for _ in range(2):
                try:
                    await bot.send_message(user_id, body, reply_markup=markup)
                    break
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                except Exception:  # noqa: BLE001 — заблокировал бота и т.п.
                    break
            if i % EMPIRE_ANNOUNCE_BATCH_SIZE == 0:
                await asyncio.sleep(EMPIRE_ANNOUNCE_BATCH_PAUSE_SECONDS)
    except Exception:
        log.exception("Empire event %s push failed", started.event_id)


async def send_finished(bot: Bot, session: AsyncSession, finished: list[ev.Finished]) -> None:
    """Итоги: императору — сводка, победителям турнира — приз."""
    for f in finished:
        text = t.PUSH_FINISHED.format(
            title=t.TITLES[f.kind], spent=format_number(f.spent), claims=f.claims, refund=format_number(f.refund),
        )
        await notify_player(bot, session, f.emperor_id, NOTIFY_EMPEROR, text)
        for place, (uid, wins, prize) in enumerate(f.winners, 1):
            await notify_player(
                bot, session, uid, NOTIFY_EMPEROR, t.PUSH_PRIZE.format(place=place, wins=wins, prize=format_number(prize)),
            )
