"""События на карте (репозиторий). Функции записи НЕ коммитят — коммитит сервис."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.event import FRAGMENT_GENIUS, FRAGMENT_PATH, FRAGMENT_TECHNIQUE
from bot.db.models.clan import ClanMember
from bot.db.models.map_event import MapEvent, MapEventEntry
from bot.db.models.user import User

# Колонки-валюты, которые можно начислять наградой (защита от подстановки имени колонки).
_CURRENCIES = frozenset({FRAGMENT_PATH, FRAGMENT_TECHNIQUE, FRAGMENT_GENIUS, "blood_drops"})


async def list_active(session: AsyncSession, user_id: int) -> Sequence[tuple[MapEvent, bool, bool]]:
    """Живые события + (победил ли игрок, законнектился ли) — одним запросом."""
    rows = await session.execute(
        select(MapEvent, MapEventEntry.won, MapEventEntry.connected)
        .outerjoin(MapEventEntry, (MapEventEntry.event_id == MapEvent.id) & (MapEventEntry.user_id == user_id))
        .where(MapEvent.ends_at > func.now(), _visible_to(user_id))
        .order_by(MapEvent.kind, MapEvent.started_at)
    )
    return [(e, bool(won), bool(connected)) for e, won, connected in rows.all()]


def _visible_to(user_id: int):
    """Общие события и клановые события клана игрока (Сторожевая башня, Додзё)."""
    clan = select(ClanMember.clan_id).where(ClanMember.user_id == user_id).scalar_subquery()
    return MapEvent.clan_id.is_(None) | (MapEvent.clan_id == clan)


async def active_codes(session: AsyncSession, kind: str, clan_id: int | None = None) -> set[str]:
    """Коды живых событий вида: общих (`clan_id=None`) или конкретного клана."""
    owner = MapEvent.clan_id.is_(None) if clan_id is None else MapEvent.clan_id == clan_id
    rows = await session.scalars(select(MapEvent.code).where(MapEvent.kind == kind, MapEvent.ends_at > func.now(), owner))
    return set(rows.all())


async def create(session: AsyncSession, kind: str, code: str, ends_at: datetime, clan_id: int | None = None) -> MapEvent:
    event = MapEvent(kind=kind, code=code, ends_at=ends_at, clan_id=clan_id)
    session.add(event)
    await session.flush()
    return event


async def get_active(session: AsyncSession, event_id: int, user_id: int | None = None) -> MapEvent | None:
    """Живое событие; с `user_id` — только видимое этому игроку (клановое — своему клану)."""
    stmt = select(MapEvent).where(MapEvent.id == event_id, MapEvent.ends_at > func.now())
    if user_id is not None:
        stmt = stmt.where(_visible_to(user_id))
    return await session.scalar(stmt)


async def lock_entry(session: AsyncSession, event_id: int, user_id: int) -> MapEventEntry:
    """Строка участия под `FOR UPDATE` (создаётся при первом заходе) — победа и коннект не
    задвоятся при двойном клике."""
    await session.execute(
        pg_insert(MapEventEntry).values(event_id=event_id, user_id=user_id).on_conflict_do_nothing()
    )
    return await session.scalar(
        select(MapEventEntry)
        .where(MapEventEntry.event_id == event_id, MapEventEntry.user_id == user_id)
        .with_for_update()
    )


async def grant_currency(session: AsyncSession, user_id: int, column: str, amount: int) -> None:
    if column not in _CURRENCIES:
        raise ValueError(column)
    if amount:
        await session.execute(
            update(User).where(User.id == user_id).values({column: getattr(User, column) + amount})
        )


async def recently_active_mutes(session: AsyncSession, days: int) -> list[tuple[int, list[str]]]:
    """Кому слать пуш о новом событии — заходившие за `days` дней и прошедшие онбординг,
    плюс выключенные игроком категории пушей (`users.notify_muted`)
    — одним запросом, чтобы рассылка отфильтровала каждого без похода в БД на получателя."""
    rows = await session.execute(
        select(User.id, User.notify_muted).where(
            User.city_id.is_not(None), User.last_active_at >= func.now() - timedelta(days=days)
        )
    )
    return [(r[0], list(r[1] or ())) for r in rows.all()]


async def purge_old(session: AsyncSession, keep_days: int = 7) -> None:
    """Старые события (и участие — каскадом) — не копить мёртвые строки."""
    await session.execute(
        text("DELETE FROM map_events WHERE ends_at < now() - make_interval(days => :d)"), {"d": keep_days}
    )
