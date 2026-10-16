"""Battle Pass (сервис). Механика — как в Universe Anime Planet (`services/battle_pass` там):
две ветки, клейм любой ячейки (high-water mark сплошного префикса + спарс-таблица уровней,
забранных вне очереди) или «всё разом», дневной буст. Отличие LBP: уровень растёт от опыта за
ежедневные задания (`services/quest`), а не от UBP. Сезон — 30 дней, создаётся лениво при
первом обращении после окончания предыдущего (шедулер не нужен).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import action_lock
from bot.config.battle_pass import (
    BP_BOOST_LEVELS,
    BP_BOOST_MULTIPLIER,
    BP_LEVEL_XP,
    BP_LEVELS_PER_PAGE,
    BP_SEASON_DAYS,
    ITEM_SCROLL,
    free_reward,
    level_from_xp,
    premium_reward,
)
from bot.config.game import ACTION_LOCK_MS
from bot.config.quest import QUEST_DAY_TZ
from bot.constant.battle_pass import LOCK_ACTION_BP, TRACK_FREE, TRACK_PREMIUM, TRACKS
from bot.constant.dev_quest import TASK_BP_CLAIM
from bot.db.models.battle_pass import BattlePass, BpSeason
from bot.db.repositories import battle_pass as bp_repo
from bot.services.resource import grant


class BattlePassBusyError(Exception):
    pass


class LevelLockedError(Exception):
    pass


class LevelAlreadyClaimedError(Exception):
    pass


class NotPremiumError(Exception):
    pass


class NothingToClaimError(Exception):
    pass


class AlreadyPremiumError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class LevelEntry:
    level: int
    free: dict[str, int]
    premium: dict[str, int]
    free_claimed: bool
    premium_claimed: bool


@dataclass(frozen=True, slots=True)
class BoostStatus:
    multiplier: int  # текущий множитель опыта (×4 или ×1)
    used: int
    cap: int
    resets_in: int  # секунд до полуночи по Москве


@dataclass(frozen=True, slots=True)
class PassPage:
    season_number: int
    season_left: int  # секунд до конца сезона
    level: int
    xp_in_level: int
    is_premium: bool
    claimed_free: int
    claimed_premium: int
    page: int
    pages_max: int
    entries: list[LevelEntry]
    boost: BoostStatus
    scrolls: int

    def unclaimed(self, track: str) -> bool:
        """Есть ли что забрать по ветке (по high-water mark; уровни вне очереди — мелочь)."""
        if track == TRACK_PREMIUM and not self.is_premium:
            return False
        return (self.claimed_premium if track == TRACK_PREMIUM else self.claimed_free) < self.level


@dataclass(frozen=True, slots=True)
class ClaimResult:
    reward: dict[str, int]
    count: int
    level: int  # текущий уровень игрока (куда переключить ленту)


def _today() -> date:
    return datetime.now(QUEST_DAY_TZ).date()


def _seconds_to_midnight() -> int:
    now = datetime.now(QUEST_DAY_TZ)
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), QUEST_DAY_TZ)
    return int((midnight - now).total_seconds())


def reward_for(track: str, level: int) -> dict[str, int]:
    return premium_reward(level) if track == TRACK_PREMIUM else free_reward(level)


def _merge(total: dict[str, int], add: dict[str, int]) -> None:
    for code, amount in add.items():
        total[code] = total.get(code, 0) + amount


async def current_season(session: AsyncSession) -> BpSeason:
    """Активный сезон; если истёк — сразу открывается следующий (ON CONFLICT по номеру)."""
    now = datetime.now(timezone.utc)
    season = await bp_repo.current_season(session, now)
    if season is not None:
        return season
    last = await bp_repo.last_season(session)
    number = (last.number + 1) if last else 1
    await bp_repo.create_season(session, number, now, now + timedelta(days=BP_SEASON_DAYS))
    await session.flush()
    season = await bp_repo.current_season(session, now)
    assert season is not None
    return season


def _boost_used(bp: BattlePass, today: date) -> int:
    return bp.boost_levels if bp.boost_day == today else 0


async def add_xp(session: AsyncSession, user_id: int, amount: int) -> int:
    """Опыт пасса за задания. Первые `BP_BOOST_LEVELS` уровней за день — опыт ×`BP_BOOST_MULTIPLIER`
    (ленивый сброс по `boost_day`, по Москве). → новый уровень. НЕ коммитит (шаг транзакции
    действия игрока)."""
    from bot.services.admin.live_config import get as live_get

    amount = int(amount * live_get("bp_xp_multiplier"))  # множитель админа «на лету» — до буста
    if amount <= 0:
        return 0
    season = await current_season(session)
    bp = await bp_repo.lock(session, user_id, season.id)
    today = _today()
    used = _boost_used(bp, today)
    level_before = level_from_xp(bp.xp)
    remaining = BP_BOOST_LEVELS - used
    if remaining > 0:
        boost_end = (level_before + remaining) * BP_LEVEL_XP  # опыт, на котором буст кончится
        boosted = amount * BP_BOOST_MULTIPLIER
        if bp.xp + boosted <= boost_end:
            new_xp = bp.xp + boosted
        else:
            raw_spent = -(-(boost_end - bp.xp) // BP_BOOST_MULTIPLIER)
            new_xp = boost_end + max(amount - raw_spent, 0)
        gained = min(level_from_xp(new_xp), level_before + remaining) - level_before
        bp.boost_levels, bp.boost_day = used + gained, today
    else:
        new_xp = bp.xp + amount
    bp.xp = new_xp
    await session.flush()
    return level_from_xp(new_xp)


async def _lock(redis: Redis, user_id: int) -> str:
    key = action_lock(user_id, LOCK_ACTION_BP)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise BattlePassBusyError
    return key


async def _grant(session: AsyncSession, user_id: int, reward: dict[str, int]) -> None:
    for code, amount in reward.items():
        if code == ITEM_SCROLL:
            await bp_repo.add_skip_scrolls(session, user_id, amount)
        else:
            await grant(session, user_id, code, amount)


def _hwm(bp: BattlePass, track: str) -> int:
    return bp.claimed_premium if track == TRACK_PREMIUM else bp.claimed_free


def _set_hwm(bp: BattlePass, track: str, value: int) -> None:
    if track == TRACK_PREMIUM:
        bp.claimed_premium = value
    else:
        bp.claimed_free = value


async def _emit_claims(session: AsyncSession, user_id: int, count: int) -> None:
    from bot.services.dev_quest import emit  # dev_quest → quest → battle_pass: ленивый импорт

    await emit(session, user_id, TASK_BP_CLAIM, count)


async def claim_level(session: AsyncSession, redis: Redis, user_id: int, track: str, level: int) -> ClaimResult:
    """Забрать ровно один уровень одной ветки — в любом порядке (как в UAP 2026-08-11)."""
    if track not in TRACKS or level < 1:
        raise LevelLockedError
    key = await _lock(redis, user_id)
    try:
        season = await current_season(session)
        bp = await bp_repo.lock(session, user_id, season.id)
        current = level_from_xp(bp.xp)
        if level > current:
            raise LevelLockedError
        if track == TRACK_PREMIUM and not bp.is_premium:
            raise NotPremiumError
        hwm = _hwm(bp, track)
        if level <= hwm:
            raise LevelAlreadyClaimedError
        if level == hwm + 1:
            # Сдвигаем high-water mark и «поглощаем» уже забранные следом уровни.
            new_hwm = level
            for claimed in await bp_repo.claimed_levels(session, user_id, season.id, track, level):
                if claimed != new_hwm + 1:
                    break
                new_hwm = claimed
            _set_hwm(bp, track, new_hwm)
            await bp_repo.drop_claims(session, user_id, season.id, track, new_hwm)
        elif not await bp_repo.add_claim(session, user_id, season.id, track, level):
            raise LevelAlreadyClaimedError
        reward = reward_for(track, level)
        await _grant(session, user_id, reward)
        await session.flush()
        await _emit_claims(session, user_id, 1)
        await session.commit()
        return ClaimResult(reward, 1, current)
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def claim_all(session: AsyncSession, redis: Redis, user_id: int, track: str) -> ClaimResult:
    """Забрать всё незабранное по ветке до текущего уровня (пропуская забранное вне очереди)."""
    if track not in TRACKS:
        raise NothingToClaimError
    key = await _lock(redis, user_id)
    try:
        season = await current_season(session)
        bp = await bp_repo.lock(session, user_id, season.id)
        if track == TRACK_PREMIUM and not bp.is_premium:
            raise NotPremiumError
        current, hwm = level_from_xp(bp.xp), _hwm(bp, track)
        if current <= hwm:
            raise NothingToClaimError
        skip = set(await bp_repo.claimed_levels(session, user_id, season.id, track, hwm))
        total: dict[str, int] = {}
        count = 0
        for level in range(hwm + 1, current + 1):
            if level not in skip:
                _merge(total, reward_for(track, level))
                count += 1
        if count == 0:
            raise NothingToClaimError
        _set_hwm(bp, track, current)
        await bp_repo.drop_claims(session, user_id, season.id, track, current)
        await _grant(session, user_id, total)
        await session.flush()
        await _emit_claims(session, user_id, count)
        await session.commit()
        return ClaimResult(total, count, current)
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


class NotEnoughDonateError(Exception):
    def __init__(self, price: int, balance: int) -> None:
        self.price = price
        self.balance = balance


async def buy_premium(session: AsyncSession, redis: Redis, user_id: int) -> None:
    """Платная ветка текущего сезона за донат-коины: списание и флаг — одна транзакция под
    `FOR UPDATE` строки пасса. Коммитит."""
    from bot.db.repositories import donate as donate_repo
    from bot.services.admin.live_config import get as live_get

    price = live_get("bp_premium_price")
    key = await _lock(redis, user_id)
    try:
        season = await current_season(session)
        bp = await bp_repo.lock(session, user_id, season.id)
        if bp.is_premium:
            raise AlreadyPremiumError
        if not await donate_repo.spend(session, user_id, price):
            raise NotEnoughDonateError(price, await donate_repo.balance(session, user_id))
        bp.is_premium = True
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def set_premium(session: AsyncSession, user_id: int) -> None:
    """Открыть платную ветку на текущий сезон (донат/админ). НЕ коммитит."""
    season = await current_season(session)
    bp = await bp_repo.lock(session, user_id, season.id)
    if bp.is_premium:
        raise AlreadyPremiumError
    bp.is_premium = True
    await session.flush()


def page_for_level(level: int, per_page: int = BP_LEVELS_PER_PAGE) -> int:
    return max(level - 1, 0) // per_page + 1


async def get_page(session: AsyncSession, user_id: int, page: int | None = None) -> PassPage:
    """Страница ленты уровней. Без `page` — страница с первым незабранным уровнем."""
    season = await current_season(session)
    bp = await bp_repo.get(session, user_id, season.id)
    xp = bp.xp if bp else 0
    claimed_free = bp.claimed_free if bp else 0
    claimed_premium = bp.claimed_premium if bp else 0
    is_premium = bool(bp and bp.is_premium)
    level = level_from_xp(xp)
    pages_max = page_for_level(level + BP_LEVELS_PER_PAGE)  # уровни бесконечны — показываем чуть вперёд
    if page is None:
        first = min(claimed_free, claimed_premium) if is_premium else claimed_free
        page = page_for_level(min(first + 1, max(level, 1)))
    page = max(1, min(page, pages_max))
    low = (page - 1) * BP_LEVELS_PER_PAGE + 1
    high = low + BP_LEVELS_PER_PAGE - 1
    extra = await bp_repo.claimed_in_range(session, user_id, season.id, low, high) if bp else set()
    entries = [
        LevelEntry(
            lvl, free_reward(lvl), premium_reward(lvl),
            lvl <= claimed_free or (TRACK_FREE, lvl) in extra,
            lvl <= claimed_premium or (TRACK_PREMIUM, lvl) in extra,
        )
        for lvl in range(low, high + 1)
    ]
    today = _today()
    used = _boost_used(bp, today) if bp else 0
    boost = BoostStatus(
        BP_BOOST_MULTIPLIER if used < BP_BOOST_LEVELS else 1, used, BP_BOOST_LEVELS, _seconds_to_midnight()
    )
    left = int((season.ends_at - datetime.now(timezone.utc)).total_seconds())
    return PassPage(
        season.number, max(left, 0), level, xp % BP_LEVEL_XP, is_premium, claimed_free, claimed_premium,
        page, pages_max, entries, boost, await bp_repo.skip_scrolls(session, user_id),
    )


async def scroll_count(session: AsyncSession, user_id: int) -> int:
    return await bp_repo.skip_scrolls(session, user_id)
