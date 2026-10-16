"""PvP-покер — столы и раздачи (сервис). Перенос из 1.0 (`poker_service.py`), правила те же:
стол набирает 2–6 игроков за бай-ин NHCoin, после ожидания раздачи идут подряд, пока за
столом ≥2 игроков со стеком; фолд — отказ от раздачи, не выход; «Уйти» — стек на баланс
после текущей раздачи. Отличия от 1.0: любое изменение стола берёт его строку `FOR UPDATE`
(ходы и таймауты не сойдутся в одну раздачу), ход проверяет номер раздачи (старая кнопка не
сыграет в новой), деньги — через реестр ресурсов, игрок сидит максимум за одним столом.

Каждая операция — одна транзакция с commit. Возвращает `PokerEvent` — что показать игрокам
(`handlers/poker` перерисовывает экран стола каждому).
"""
from __future__ import annotations

from bot.constant.dev_quest import TASK_POKER_HAND

from bot.services.dev_quest import emit as quest_event

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.poker import (
    POKER_ACTION_TIMEOUT_SECONDS,
    POKER_BIG_BLIND_RATIO,
    POKER_BUY_INS,
    POKER_LOBBY_LIMIT,
    POKER_MAX_PLAYERS,
    POKER_MIN_PLAYERS,
    POKER_RAKE_PERCENT,
    POKER_SMALL_BLIND_RATIO,
    POKER_WAIT_OPTIONS_SECONDS,
)
from bot.constant.poker import (
    ACT_CALL,
    ACT_CHECK,
    ACT_FOLD,
    ACT_RAISE,
    PLAYER_ACTIVE,
    PLAYER_ALL_IN,
    PLAYER_FOLDED,
    STREET_SHOWDOWN,
    STREETS,
    TABLE_ACTIVE,
    TABLE_CANCELLED,
    TABLE_FINISHED,
    TABLE_WAITING,
)
from bot.constant.resource import RES_COINS
from bot.db.models.poker import PokerPlayer, PokerTable
from bot.services.poker.engine import new_deck, showdown
from bot.services.resource import grant, spend


class PokerError(Exception):
    """Ошибка действия игрока — текст ключа для экрана (`texts/poker.ERRORS`)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class PokerEvent:
    table_id: int
    kind: str  # created | joined | started | action | hand_finished | cancelled | left
    user_ids: list[int] = field(default_factory=list)  # кому показать (все за столом + ушедшие)
    result: dict | None = None  # итог раздачи: банк, борд, карты, выигрыши


@dataclass(frozen=True, slots=True)
class LobbyTable:
    id: int
    buy_in: int
    players: int
    max_players: int
    starts_in: int


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _players(session: AsyncSession, table_id: int) -> list[PokerPlayer]:
    return list((await session.scalars(select(PokerPlayer).where(PokerPlayer.table_id == table_id).order_by(PokerPlayer.seat))).all())


async def _lock_table(session: AsyncSession, table_id: int) -> PokerTable | None:
    return await session.scalar(select(PokerTable).where(PokerTable.id == table_id).with_for_update())


async def seat_of(session: AsyncSession, user_id: int) -> int | None:
    """Стол, за которым игрок сидит (ждёт или играет), или None."""
    return await session.scalar(
        select(PokerTable.id)
        .join(PokerPlayer, PokerPlayer.table_id == PokerTable.id)
        .where(PokerPlayer.user_id == user_id, PokerTable.status.in_((TABLE_WAITING, TABLE_ACTIVE)))
        .limit(1)
    )


async def lobby(session: AsyncSession) -> list[LobbyTable]:
    rows = await session.execute(
        select(PokerTable, func.count(PokerPlayer.id))
        .join(PokerPlayer, PokerPlayer.table_id == PokerTable.id)
        .where(PokerTable.status == TABLE_WAITING)
        .group_by(PokerTable.id)
        .order_by(PokerTable.created_at.desc())
        .limit(POKER_LOBBY_LIMIT)
    )
    now = _now()
    return [
        LobbyTable(t.id, t.buy_in, n, t.max_players, max(0, int((t.starts_at - now).total_seconds())))
        for t, n in rows.all()
    ]


async def get_table(session: AsyncSession, table_id: int) -> tuple[PokerTable | None, list[PokerPlayer]]:
    table = await session.get(PokerTable, table_id, populate_existing=True)
    return table, (await _players(session, table_id) if table else [])


async def create(session: AsyncSession, user_id: int, buy_in: int, max_players: int, wait_seconds: int) -> PokerEvent:
    if buy_in not in POKER_BUY_INS or not POKER_MIN_PLAYERS <= max_players <= POKER_MAX_PLAYERS or wait_seconds not in POKER_WAIT_OPTIONS_SECONDS:
        raise PokerError("bad_params")
    if await seat_of(session, user_id):
        raise PokerError("already_seated")
    if not await spend(session, user_id, RES_COINS, buy_in):
        raise PokerError("no_coins")
    table = PokerTable(
        creator_id=user_id, buy_in=buy_in, max_players=max_players,
        big_blind=max(2, buy_in // POKER_BIG_BLIND_RATIO), small_blind=max(1, buy_in // POKER_SMALL_BLIND_RATIO),
        starts_at=_now() + timedelta(seconds=wait_seconds),
    )
    session.add(table)
    await session.flush()
    session.add(PokerPlayer(table_id=table.id, user_id=user_id, seat=0, stack=buy_in))
    await session.commit()
    return PokerEvent(table.id, "created", [user_id])


async def join(session: AsyncSession, user_id: int, table_id: int, rng: random.Random | None = None) -> PokerEvent:
    if await seat_of(session, user_id):
        raise PokerError("already_seated")
    table = await _lock_table(session, table_id)
    if table is None or table.status != TABLE_WAITING:
        raise PokerError("table_gone")
    players = await _players(session, table_id)
    if len(players) >= table.max_players:
        raise PokerError("table_full")
    if not await spend(session, user_id, RES_COINS, table.buy_in):
        raise PokerError("no_coins")
    player = PokerPlayer(table_id=table.id, user_id=user_id, seat=len(players), stack=table.buy_in)
    session.add(player)
    await session.flush()
    players.append(player)
    kind = "joined"
    if len(players) >= table.max_players:
        _start_hand(table, players, rng)
        kind = "started"
    await session.commit()
    return PokerEvent(table.id, kind, [p.user_id for p in players])


async def leave(session: AsyncSession, user_id: int, table_id: int) -> PokerEvent:
    """Ожидание — сразу вернуть бай-ин; идёт игра — встать после текущей раздачи."""
    table = await _lock_table(session, table_id)
    if table is None:
        raise PokerError("table_gone")
    players = await _players(session, table_id)
    me = next((p for p in players if p.user_id == user_id), None)
    if me is None:
        raise PokerError("not_seated")
    everyone = [p.user_id for p in players]
    if table.status == TABLE_WAITING:
        await _cash_out(session, [me])
        if len(players) == 1:
            table.status = TABLE_CANCELLED
        await session.commit()
        return PokerEvent(table.id, "left", everyone)
    if table.status != TABLE_ACTIVE:
        raise PokerError("table_gone")
    me.leaving = True
    await session.commit()
    return PokerEvent(table.id, "leaving", [user_id])


# --- раздача ---

def _post(table: PokerTable, player: PokerPlayer, amount: int) -> None:
    amount = min(amount, player.stack)
    player.stack -= amount
    player.round_bet += amount
    player.total_bet += amount
    table.pot += amount
    if player.stack == 0:
        player.status = PLAYER_ALL_IN


def _deadline() -> datetime:
    return _now() + timedelta(seconds=POKER_ACTION_TIMEOUT_SECONDS)


def _start_hand(table: PokerTable, players: list[PokerPlayer], rng: random.Random | None = None) -> None:
    players.sort(key=lambda p: p.seat)
    n = len(players)
    deck = new_deck(rng)
    for i, p in enumerate(players):
        # Места — подряд с нуля (за время ожидания кто-то мог уйти), индекс = место.
        p.seat = i
        p.status, p.round_bet, p.total_bet, p.acted, p.leaving = PLAYER_ACTIVE, 0, 0, False, False
        p.hole = json.dumps(deck[2 * i:2 * i + 2])
    table.community = json.dumps(deck[2 * n:2 * n + 5])
    table.status, table.street, table.pot = TABLE_ACTIVE, STREETS[0], 0
    table.hand_no += 1
    dealer = table.dealer_seat % n
    if n == 2:
        sb, bb, first = dealer, (dealer + 1) % n, dealer
    else:
        sb, bb = (dealer + 1) % n, (dealer + 2) % n
        first = (bb + 1) % n
    _post(table, players[sb], table.small_blind)
    _post(table, players[bb], table.big_blind)
    table.current_bet = players[bb].round_bet
    table.last_raise = table.big_blind
    table.current_seat = first if players[first].status == PLAYER_ACTIVE else _next_seat(players, first)
    table.action_deadline = _deadline()


def _next_seat(players: list[PokerPlayer], from_seat: int) -> int:
    n = len(players)
    for step in range(1, n + 1):
        p = players[(from_seat + step) % n]
        if p.status == PLAYER_ACTIVE:
            return p.seat
    return from_seat


def to_call(table: PokerTable, player: PokerPlayer) -> int:
    return max(0, table.current_bet - player.round_bet)


def min_raise_to(table: PokerTable, player: PokerPlayer) -> int:
    return min(table.current_bet + max(table.last_raise, table.big_blind), player.round_bet + player.stack)


def _apply(table: PokerTable, players: list[PokerPlayer], actor: PokerPlayer, action: str, amount: int = 0) -> None:
    owe = to_call(table, actor)
    if action == ACT_FOLD:
        actor.status = PLAYER_FOLDED
    elif action == ACT_CHECK:
        if owe > 0:
            raise PokerError("cant_check")
    elif action == ACT_CALL:
        _post(table, actor, owe)
    elif action == ACT_RAISE:
        top = actor.round_bet + actor.stack
        target = min(max(amount, min_raise_to(table, actor)), top)
        if target <= table.current_bet:
            raise PokerError("bad_raise")
        table.last_raise = max(target - table.current_bet, table.last_raise)
        _post(table, actor, target - actor.round_bet)
        table.current_bet = actor.round_bet
        for p in players:
            if p is not actor and p.status == PLAYER_ACTIVE:
                p.acted = False
    else:
        raise PokerError("bad_action")
    actor.acted = True


async def _advance(session: AsyncSession, table: PokerTable, players: list[PokerPlayer], rng) -> PokerEvent:
    active = [p for p in players if p.status == PLAYER_ACTIVE]
    alive = [p for p in players if p.status != PLAYER_FOLDED]
    if len(alive) <= 1:
        return await _finish(session, table, players, rng)
    if not all(p.round_bet == table.current_bet and p.acted for p in active):
        table.current_seat = _next_seat(players, table.current_seat)
        table.action_deadline = _deadline()
        return PokerEvent(table.id, "action", [p.user_id for p in players])
    if len(active) <= 1 or table.street == STREETS[-1]:
        return await _finish(session, table, players, rng)  # добор борда и вскрытие
    table.street = STREETS[STREETS.index(table.street) + 1]
    table.current_bet, table.last_raise = 0, table.big_blind
    for p in players:
        p.round_bet = 0
        if p.status == PLAYER_ACTIVE:
            p.acted = False
    table.current_seat = _next_seat(players, table.dealer_seat % len(players))
    table.action_deadline = _deadline()
    return PokerEvent(table.id, "action", [p.user_id for p in players])


async def _finish(session: AsyncSession, table: PokerTable, players: list[PokerPlayer], rng) -> PokerEvent:
    alive = [p for p in players if p.status != PLAYER_FOLDED]
    community = json.loads(table.community)
    if len(alive) == 1:
        rake = int(table.pot * POKER_RAKE_PERCENT)
        payouts = {p.user_id: 0 for p in players}
        payouts[alive[0].user_id] = table.pot - rake
        hands, shown = {}, []
    else:
        res = showdown(
            [{"user_id": p.user_id, "hole": json.loads(p.hole), "total_bet": p.total_bet, "folded": p.status == PLAYER_FOLDED} for p in players],
            community, POKER_RAKE_PERCENT,
        )
        payouts, hands, rake = res["payouts"], res["hands"], res["rake"]
        shown = community
    result = {
        "hand_no": table.hand_no,
        "pot": table.pot,
        "rake": rake,
        "board": shown,
        "showdown": len(alive) > 1,
        "players": [
            {
                "user_id": p.user_id, "hole": json.loads(p.hole) if len(alive) > 1 and p.status != PLAYER_FOLDED else [],
                "hand": list(hands.get(p.user_id, ())), "won": payouts.get(p.user_id, 0), "bet": p.total_bet,
            }
            for p in players
        ],
    }
    for uid in sorted(p.user_id for p in players):
        await quest_event(session, uid, TASK_POKER_HAND)
    everyone = [p.user_id for p in players]
    for p in players:
        p.stack += payouts.get(p.user_id, 0)
    table.street, table.current_seat, table.action_deadline = STREET_SHOWDOWN, -1, None
    # Следующая раздача или закрытие: проигравшиеся в ноль и «уходящие» встают.
    stay = [p for p in players if p.stack > 0 and not p.leaving]
    await _cash_out(session, [p for p in players if p not in stay])
    if len(stay) < POKER_MIN_PLAYERS:
        await _cash_out(session, stay)
        table.status = TABLE_FINISHED
        result["closed"] = True
    else:
        for i, p in enumerate(stay):
            p.seat = i
        table.dealer_seat = (table.dealer_seat + 1) % len(stay)
        _start_hand(table, stay, rng)
    await session.flush()
    return PokerEvent(table.id, "hand_finished", everyone, result)


async def _cash_out(session: AsyncSession, players: list[PokerPlayer]) -> None:
    for p in players:
        if p.stack > 0:
            await grant(session, p.user_id, RES_COINS, p.stack)
        await session.delete(p)
    await session.flush()


async def act(session: AsyncSession, user_id: int, table_id: int, hand_no: int, action: str, amount: int = 0,
              rng: random.Random | None = None) -> PokerEvent:
    table = await _lock_table(session, table_id)
    if table is None or table.status != TABLE_ACTIVE or table.hand_no != hand_no:
        raise PokerError("hand_gone")
    players = await _players(session, table_id)
    actor = next((p for p in players if p.user_id == user_id), None)
    if actor is None:
        raise PokerError("not_seated")
    if actor.seat != table.current_seat or actor.status != PLAYER_ACTIVE:
        raise PokerError("not_your_turn")
    _apply(table, players, actor, action, amount)
    event = await _advance(session, table, players, rng)
    await session.commit()
    return event


async def tick(session_factory: async_sessionmaker[AsyncSession], rng: random.Random | None = None) -> list[PokerEvent]:
    """Фоновый проход: старт столов по истечении ожидания (или отмена с возвратом, если
    игроков меньше двух) и авто-ход по таймауту (чек, если можно, иначе фолд). Каждый стол —
    своя транзакция."""
    now = _now()
    async with session_factory() as session:
        due_start = list((await session.scalars(select(PokerTable.id).where(PokerTable.status == TABLE_WAITING, PokerTable.starts_at <= now))).all())
        due_act = list((await session.scalars(select(PokerTable.id).where(
            PokerTable.status == TABLE_ACTIVE, PokerTable.action_deadline.is_not(None), PokerTable.action_deadline <= now
        ))).all())
    events = []
    for table_id in due_start:
        async with session_factory() as session:
            table = await _lock_table(session, table_id)
            if table is None or table.status != TABLE_WAITING or table.starts_at > _now():
                continue
            players = await _players(session, table_id)
            everyone = [p.user_id for p in players]
            if len(players) >= POKER_MIN_PLAYERS:
                _start_hand(table, players, rng)
                kind = "started"
            else:
                await _cash_out(session, players)
                table.status = TABLE_CANCELLED
                kind = "cancelled"
            await session.commit()
            events.append(PokerEvent(table_id, kind, everyone))
    for table_id in due_act:
        async with session_factory() as session:
            table = await _lock_table(session, table_id)
            if table is None or table.status != TABLE_ACTIVE or table.action_deadline is None or table.action_deadline > _now():
                continue
            players = await _players(session, table_id)
            actor = next((p for p in players if p.seat == table.current_seat), None)
            if actor is not None and actor.status == PLAYER_ACTIVE:
                _apply(table, players, actor, ACT_CHECK if to_call(table, actor) == 0 else ACT_FOLD)
            event = await _advance(session, table, players, rng)
            await session.commit()
            events.append(event)
    return events
