"""Топ игроков (мощь армии) и кланов, список всех игроков, награды сезона (сервис).

Пользователь 2026-10-11: сезон — это вайп (патч из админки) и раз в месяц итог сезона
Battle Pass. В обоих случаях топ-10 игроков и топ-5 кланов получают награды
(`config/top`). Мощь для сортировки — снимок `users.army_power_cache`: фоном раз в
`TOP_POWER_REFRESH_SECONDS` для заходивших за сутки и для ВСЕХ перед выплатой (честный
итог, а не устаревший снимок). Выплата — ровно один раз на ключ (`season_top_payouts`, PK).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.top import (
    TOP_CLAN_PLACES,
    TOP_PAGE_SIZE,
    TOP_PLAYER_PLACES,
    TOP_POWER_ACTIVE_HOURS,
    TOP_POWER_BATCH,
    TOP_SEASON_LOOKBACK_DAYS,
    clan_reward,
    player_reward,
)
from bot.constant.top import PAYOUT_KEY_BP
from bot.db.repositories import battle_pass as bp_repo
from bot.db.repositories import clan as clan_repo
from bot.db.repositories import top as top_repo
from bot.db.repositories.top import PlayerRow
from bot.services.admin.mass import ticket_grant_values
from bot.services.extra import get_army_stats
from bot.texts.top import PUSH_CLAN_REWARD, PUSH_PLAYER_REWARD, reward_text
from bot.utils.notify import notify

log = logging.getLogger(__name__)


# --- мощь ---


async def refresh_powers(session_factory: async_sessionmaker[AsyncSession], *, everyone: bool = False) -> int:
    """Пересчитать снимок мощи: заходившим за сутки (фон) или всем (перед выплатой).
    Пачками со своей транзакцией — не держим одну на тысячи игроков. → сколько обновлено."""
    async with session_factory() as session:
        if everyone:
            ids = await top_repo.onboarded_user_ids(session)
        else:
            since = datetime.now(timezone.utc) - timedelta(hours=TOP_POWER_ACTIVE_HOURS)
            ids = await top_repo.active_user_ids(session, since)
    for start in range(0, len(ids), TOP_POWER_BATCH):
        async with session_factory() as session:
            values = [(uid, (await get_army_stats(session, uid)).total_power) for uid in ids[start : start + TOP_POWER_BATCH]]
            await top_repo.set_powers(session, values)
            await session.commit()
    return len(ids)


# --- экраны ---


@dataclass(frozen=True, slots=True)
class ClanRow:
    name: str
    lands: int
    members: int


@dataclass(frozen=True, slots=True)
class TopView:
    players: list[PlayerRow]
    clans: list[ClanRow]
    my_place: int | None
    my_power: int
    season_ends_in: int | None  # секунд до конца сезона Battle Pass (итог месяца); None — сезона нет


async def get_top(session: AsyncSession, user_id: int) -> TopView:
    players = await top_repo.players_page(session, TOP_PAGE_SIZE, 0)
    clans = [ClanRow(c.name, c.lands, n) for c, n in await clan_repo.top_page(session, TOP_PAGE_SIZE, 0)]
    mine = await top_repo.rank_of(session, user_id)
    now = datetime.now(timezone.utc)
    season = await bp_repo.current_season(session, now)
    return TopView(
        players=players,
        clans=clans,
        my_place=mine[0] if mine else None,
        my_power=mine[1] if mine else 0,
        season_ends_in=max(0, int((season.ends_at - now).total_seconds())) if season else None,
    )


async def get_players_page(session: AsyncSession, page: int, size: int) -> tuple[list[PlayerRow], int, int, int]:
    """→ (страница, номер страницы после зажима, всего страниц, всего игроков)."""
    total = await top_repo.count_players(session)
    pages = max(1, (total + size - 1) // size)
    page = max(0, min(page, pages - 1))
    return await top_repo.players_page(session, size, page * size), page, pages, total


# --- награды сезона ---


@dataclass(frozen=True, slots=True)
class Winner:
    user_id: int
    place: int
    donate: int
    coins: int
    tickets: int
    clan: str | None = None  # награда за место клана (иначе — личная)


async def snapshot_winners(session_factory: async_sessionmaker[AsyncSession]) -> list[Winner]:
    """Пересчитать мощь всем и снять победителей (до патча — патч обнулит армии)."""
    await refresh_powers(session_factory, everyone=True)
    winners: list[Winner] = []
    async with session_factory() as session:
        for place, row in enumerate(await top_repo.players_page(session, TOP_PLAYER_PLACES, 0), start=1):
            donate, coins, tickets = player_reward(place)
            if row.power > 0 and (donate or coins or tickets):
                winners.append(Winner(row.user_id, place, donate, coins, tickets))
        for place, (clan, _) in enumerate(await clan_repo.top_page(session, TOP_CLAN_PLACES, 0), start=1):
            donate, coins, tickets = clan_reward(place)
            if clan.lands <= 0 or not (donate or coins or tickets):
                continue
            winners.extend(
                Winner(uid, place, donate, coins, tickets, clan=clan.name) for uid in await clan_repo.member_ids(session, clan.id)
            )
    return winners


async def award(bot: Bot | None, session_factory: async_sessionmaker[AsyncSession], key: str, winners: list[Winner]) -> bool:
    """Начислить снятых победителей ровно один раз на `key` (одна транзакция) и разослать пуши.
    → False — по этому ключу уже выплачено."""
    async with session_factory() as session:
        if not await top_repo.claim_payout(session, key):
            await session.rollback()
            return False
        for w in winners:
            await top_repo.credit(
                session, w.user_id, donate=w.donate, coins=w.coins,
                ticket_values=ticket_grant_values(w.tickets) if w.tickets else {},
            )
        await session.commit()
    if bot is not None:
        for w in winners:
            reward = reward_text(w.donate, w.coins, w.tickets)
            text_ = (
                PUSH_CLAN_REWARD.format(clan=w.clan, place=w.place, reward=reward)
                if w.clan
                else PUSH_PLAYER_REWARD.format(place=w.place, reward=reward)
            )
            await notify(bot, w.user_id, text_)
    log.info("Season top paid: %s, %d rewards", key, len(winners))
    return True


async def sweep_seasons(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Итог месяца: сезон Battle Pass закончился — выплатить топ (если ещё не выплачен)."""
    since = datetime.now(timezone.utc) - timedelta(days=TOP_SEASON_LOOKBACK_DAYS)
    async with session_factory() as session:
        numbers = await top_repo.unpaid_ended_seasons(session, since)
    for number in numbers:
        await award(bot, session_factory, PAYOUT_KEY_BP.format(number=number), await snapshot_winners(session_factory))
