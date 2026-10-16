"""Казино — слоты и блэкджек (сервис). Правила и числа — из 1.0 (`config/casino`).

Слоты: ставка списывается, три барабана, тройка — множитель символа, пара — ставка
назад; всё одной транзакцией. Блэкджек: ставка списывается при раздаче, сама раздача (карты
и ставка) живёт в Redis с TTL — брошенная раздача сгорает вместе со ставкой. Итог раздачи
забирается атомарным `GETDEL` до выплаты: двойной клик «Хватит» не выплатит дважды.
"""
from __future__ import annotations

from bot.constant.dev_quest import TASK_CASINO

from bot.services.dev_quest import emit as quest_event

import json
import random
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import action_lock, blackjack_hand
from bot.config.casino import (
    BLACKJACK_DEALER_STAND,
    BLACKJACK_HAND_TTL_SECONDS,
    BLACKJACK_NATURAL_MULTIPLIER,
    BLACKJACK_STATISTS_MIN,
    BLACKJACK_WIN_MULTIPLIER,
    SLOTS_PAIR_MULTIPLIER,
    SLOTS_SYMBOLS,
)
from bot.config.game import ACTION_LOCK_MS
from bot.constant.casino import GAME_BLACKJACK, GAME_SLOTS, LOCK_ACTION_CASINO, STAKE_RESOURCE, STAKE_STATIST
from bot.services.casino.common import (
    CasinoBusyError,
    InvalidStakeError,
    NotEnoughError,
    Stake,
    check_x3,
    pay_stake,
    take_stake,
)

OUTCOME_TRIPLE = "triple"
OUTCOME_PAIR = "pair"
OUTCOME_LOSS = "loss"
BJ_WIN = "win"
BJ_NATURAL = "natural"
BJ_PUSH = "push"
BJ_LOSS = "loss"
BJ_BUST = "bust"


class HandNotFoundError(Exception):
    pass


class HandInProgressError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SlotsResult:
    reel: tuple[str, str, str]
    outcome: str
    stake: Stake
    payout: int


@dataclass(frozen=True, slots=True)
class BlackjackState:
    player: list[list]  # карты [ранг, масть]
    dealer: list[list]
    stake: Stake
    doubled: bool
    finished: bool
    outcome: str = ""
    payout: int = 0

    @property
    def player_total(self) -> int:
        return hand_value(self.player)

    @property
    def dealer_total(self) -> int:
        return hand_value(self.dealer)


async def _lock(redis: Redis, user_id: int) -> str:
    key = action_lock(user_id, LOCK_ACTION_CASINO)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise CasinoBusyError
    return key


# --- слоты ---

def spin(rng: random.Random) -> tuple[str, str, str]:
    symbols = list(SLOTS_SYMBOLS)
    weights = [SLOTS_SYMBOLS[s][0] for s in symbols]
    return tuple(rng.choices(symbols, weights=weights, k=3))  # type: ignore[return-value]


def slots_payout(reel: tuple[str, str, str], amount: int) -> tuple[str, int]:
    counts = {s: reel.count(s) for s in set(reel)}
    if 3 in counts.values():
        symbol = reel[0]
        return OUTCOME_TRIPLE, amount * SLOTS_SYMBOLS[symbol][1]
    if 2 in counts.values():
        return OUTCOME_PAIR, int(amount * SLOTS_PAIR_MULTIPLIER)
    return OUTCOME_LOSS, 0


async def play_slots(session: AsyncSession, redis: Redis, user_id: int, stake: Stake, rng: random.Random | None = None) -> SlotsResult:
    if stake.kind != STAKE_RESOURCE:
        raise InvalidStakeError
    stake.validate()
    key = await _lock(redis, user_id)
    try:
        await check_x3(redis, user_id, GAME_SLOTS, stake)
        await take_stake(session, user_id, stake)
        reel = spin(rng or random.Random())
        outcome, payout = slots_payout(reel, stake.amount)
        await pay_stake(session, user_id, stake, payout)
        await quest_event(session, user_id, TASK_CASINO)
        await session.commit()
        return SlotsResult(reel, outcome, stake, payout)
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


# --- блэкджек ---

RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
SUITS = ("♠", "♥", "♦", "♣")


def hand_value(cards: list[list]) -> int:
    total, aces = 0, 0
    for rank, _ in cards:
        if rank == "A":
            aces += 1
            total += 11
        elif rank in ("J", "Q", "K"):
            total += 10
        else:
            total += int(rank)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def _draw(rng: random.Random) -> list:
    return [rng.choice(RANKS), rng.choice(SUITS)]


def _settle(player: list[list], dealer: list[list], stake: Stake, doubled: bool, rng: random.Random) -> tuple[list[list], str, int]:
    """Добор дилера до порога и итог. → (карты дилера, исход, выплата)."""
    bet = stake.amount * (2 if doubled else 1)
    pv = hand_value(player)
    if pv > 21:
        return dealer, BJ_BUST, 0
    while hand_value(dealer) < BLACKJACK_DEALER_STAND:
        dealer = dealer + [_draw(rng)]
    dv = hand_value(dealer)
    if dv > 21 or pv > dv:
        return dealer, BJ_WIN, int(bet * BLACKJACK_WIN_MULTIPLIER)
    if pv == dv:
        return dealer, BJ_PUSH, bet
    return dealer, BJ_LOSS, 0


def _to_json(player, dealer, stake: Stake, doubled: bool) -> str:
    return json.dumps({"player": player, "dealer": dealer, "stake": stake.to_dict(), "doubled": doubled})


async def current_hand(redis: Redis, user_id: int) -> BlackjackState | None:
    raw = await redis.get(blackjack_hand(user_id))
    if raw is None:
        return None
    data = json.loads(raw)
    return BlackjackState(data["player"], data["dealer"], Stake.of(data["stake"]), data["doubled"], False)


async def blackjack_deal(session: AsyncSession, redis: Redis, user_id: int, stake: Stake, rng: random.Random | None = None) -> BlackjackState:
    """Раздача: ставка списывается (commit), две карты игроку, две дилеру (одна скрыта). Блэкджек
    с двух карт — сразу выплата ×2.5 (если у дилера не тоже 21)."""
    stake.validate()
    if stake.kind == STAKE_STATIST and stake.amount < BLACKJACK_STATISTS_MIN:
        raise InvalidStakeError
    rng = rng or random.Random()
    key = await _lock(redis, user_id)
    try:
        if await redis.exists(blackjack_hand(user_id)):
            raise HandInProgressError
        await check_x3(redis, user_id, GAME_BLACKJACK, stake)
        await take_stake(session, user_id, stake)
        await quest_event(session, user_id, TASK_CASINO)
        player, dealer = [_draw(rng), _draw(rng)], [_draw(rng), _draw(rng)]
        if hand_value(player) == 21:
            if hand_value(dealer) == 21:
                outcome, payout = BJ_PUSH, stake.amount
            else:
                outcome, payout = BJ_NATURAL, int(stake.amount * BLACKJACK_NATURAL_MULTIPLIER)
            await pay_stake(session, user_id, stake, payout)
            await session.commit()
            return BlackjackState(player, dealer, stake, False, True, outcome, payout)
        await session.commit()
        await redis.set(blackjack_hand(user_id), _to_json(player, dealer, stake, False), ex=BLACKJACK_HAND_TTL_SECONDS)
        return BlackjackState(player, dealer, stake, False, False)
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def _finish(session: AsyncSession, redis: Redis, user_id: int, player, dealer, stake: Stake, doubled: bool, rng) -> BlackjackState:
    """Забрать раздачу атомарно (GETDEL) и выплатить — второй вызов найдёт пусто."""
    if await redis.getdel(blackjack_hand(user_id)) is None:
        raise HandNotFoundError
    dealer, outcome, payout = _settle(player, dealer, stake, doubled, rng)
    try:
        await pay_stake(session, user_id, stake, payout)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return BlackjackState(player, dealer, stake, doubled, True, outcome, payout)


async def blackjack_hit(session: AsyncSession, redis: Redis, user_id: int, rng: random.Random | None = None) -> BlackjackState:
    rng = rng or random.Random()
    key = await _lock(redis, user_id)
    try:
        hand = await current_hand(redis, user_id)
        if hand is None:
            raise HandNotFoundError
        player = hand.player + [_draw(rng)]
        if hand_value(player) >= 21:
            return await _finish(session, redis, user_id, player, hand.dealer, hand.stake, hand.doubled, rng)
        await redis.set(blackjack_hand(user_id), _to_json(player, hand.dealer, hand.stake, hand.doubled), ex=BLACKJACK_HAND_TTL_SECONDS)
        return BlackjackState(player, hand.dealer, hand.stake, hand.doubled, False)
    finally:
        await redis.delete(key)


async def blackjack_stand(session: AsyncSession, redis: Redis, user_id: int, rng: random.Random | None = None) -> BlackjackState:
    rng = rng or random.Random()
    key = await _lock(redis, user_id)
    try:
        hand = await current_hand(redis, user_id)
        if hand is None:
            raise HandNotFoundError
        return await _finish(session, redis, user_id, hand.player, hand.dealer, hand.stake, hand.doubled, rng)
    finally:
        await redis.delete(key)


async def blackjack_double(session: AsyncSession, redis: Redis, user_id: int, rng: random.Random | None = None) -> BlackjackState:
    """Удвоение (только на двух картах): доплата ставки, одна карта и сразу итог."""
    rng = rng or random.Random()
    key = await _lock(redis, user_id)
    try:
        hand = await current_hand(redis, user_id)
        if hand is None or len(hand.player) != 2 or hand.doubled:
            raise HandNotFoundError
        await take_stake(session, user_id, hand.stake)
        await session.commit()
        player = hand.player + [_draw(rng)]
        return await _finish(session, redis, user_id, player, hand.dealer, hand.stake, True, rng)
    except NotEnoughError:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)
