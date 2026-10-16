"""Тикеты на вербовку уников — регенерация раз в 30 минут, кап 10 (сервис).

raw-notes «Вербовка»: «получить уника он может за счёт тикетов, тикет получается раз в 30
минут, максимальное хранилище тикетов 10»; подтверждено пользователем 2026-09-30, 1 тикет =
1 крутка. Реген ленивый (без фонового таска) — см. `db/repositories/ticket`. Экран
показывает прогноз `get_status` — чистое чтение по той же формуле, что атомарный SQL.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.game import TICKET_CAP, TICKET_REGEN_SECONDS
from bot.db.repositories import ticket as ticket_repo
from bot.services.build import capped, get_build


@dataclass(frozen=True, slots=True)
class TicketStatus:
    count: int
    cap: int
    next_in_seconds: int | None  # None — хранилище полное, таймер стоит


@dataclass(frozen=True, slots=True)
class _Regen:
    cap: int
    interval: int


async def _regen(session: AsyncSession, user_id: int) -> _Regen:
    """Потолок и интервал регена с бафами систем развития (Элита: «вербовка уников»)."""
    eco = (await get_build(session, user_id)).eco
    return _Regen(
        cap=TICKET_CAP + eco.ticket_cap,
        interval=max(60, round(TICKET_REGEN_SECONDS * (1 - capped(eco.ticket_regen, 0.6)))),
    )


def _project(count: int, updated_at: datetime, now: datetime, regen: _Regen = _Regen(TICKET_CAP, TICKET_REGEN_SECONDS)) -> TicketStatus:
    """Та же формула, что `_SPEND_SQL`, без записи."""
    cap, interval = regen.cap, regen.interval
    if count >= cap:
        return TicketStatus(count=count, cap=cap, next_in_seconds=None)
    elapsed = max(0.0, (now - updated_at).total_seconds())
    ticks = int(elapsed // interval)
    regen_count = min(cap, count + ticks)
    if regen_count >= cap:
        return TicketStatus(count=regen_count, cap=cap, next_in_seconds=None)
    anchor = updated_at + timedelta(seconds=ticks * interval)
    next_in = int(interval - (now - anchor).total_seconds())
    return TicketStatus(count=regen_count, cap=cap, next_in_seconds=max(1, next_in))


async def get_status(session: AsyncSession, user_id: int) -> TicketStatus:
    raw = await ticket_repo.get_raw(session, user_id)
    regen = await _regen(session, user_id)
    if raw is None:
        return TicketStatus(count=0, cap=regen.cap, next_in_seconds=None)
    return _project(raw[0], raw[1], datetime.now(timezone.utc), regen)


async def spend(session: AsyncSession, user_id: int, amount: int = 1) -> TicketStatus | None:
    """Реген + списание одним UPDATE. None — не хватает. НЕ коммитит (часть крутки)."""
    regen = await _regen(session, user_id)
    result = await ticket_repo.spend(session, user_id, amount=amount, cap=regen.cap, interval_seconds=regen.interval)
    if result is None:
        return None
    return _project(result[0], result[1], datetime.now(timezone.utc), regen)


async def refund(session: AsyncSession, user_id: int, amount: int = 1) -> TicketStatus:
    """Вернуть только что списанный тикет (бесплатная крутка). НЕ коммитит."""
    await ticket_repo.refund(session, user_id, amount)
    return await get_status(session, user_id)
