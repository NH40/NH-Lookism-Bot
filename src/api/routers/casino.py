"""API-роутер Mini App: казино — слоты, блэкджек, покер.

Только `bot.services.casino` / `bot.services.poker` (те же функции, что у хендлеров). Покер за
столом — опрос состояния (`GET /poker/table/{id}`); ходы по таймауту и старт столов делает
фоновый `poker.tick` бота. Пуши соперникам в Telegram отсюда не шлём — у них стол обновляется
своим опросом или при заходе в бота.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.push import push_poker
from api.routers._common import bad, clean_label, require_user
from bot.config.casino import BLACKJACK_STATISTS_MIN, SLOTS_PAIR_MULTIPLIER, SLOTS_SYMBOLS
from bot.config.poker import (
    POKER_ACTION_TIMEOUT_SECONDS,
    POKER_BUY_INS,
    POKER_MAX_PLAYERS,
    POKER_MIN_PLAYERS,
    POKER_RAKE_PERCENT,
    POKER_WAIT_OPTIONS_SECONDS,
)
from bot.constant.casino import STAKE_RESOURCE, STAKE_STATIST
from bot.constant.poker import (
    ACT_CALL,
    ACT_CHECK,
    ACT_FOLD,
    ACT_RAISE,
    PLAYER_ALL_IN,
    PLAYER_FOLDED,
    TABLE_ACTIVE,
    TABLE_WAITING,
)
from bot.constant.resource import NO_MINT_RESOURCES, RESOURCES
from bot.db.models.gang import Gang
from bot.services import casino as casino_svc
from bot.services import poker as poker_svc
from bot.services.casino import (
    CasinoBusyError,
    HandInProgressError,
    HandNotFoundError,
    InvalidStakeError,
    NotEnoughError,
    Stake,
    X3StrategyError,
)
from bot.services.extra import list_squads
from bot.services.poker import PokerError, PokerEvent
from bot.services.poker.engine import RANK_NAMES, SUITS
from bot.services.resource import StatistKey, balances
from bot.texts.casino import (
    BUSY_ALERT,
    HAND_GONE_ALERT,
    HAND_IN_PROGRESS_ALERT,
    NOT_ENOUGH_ALERT,
    STATISTS_MIN_ALERT,
    X3_ALERT,
)
from bot.texts.poker import ERRORS as POKER_ERRORS
from bot.texts.resource import RESOURCE_NAMES, item_label
from bot.utils.formatting import format_number

router = APIRouter(prefix="/api/casino", tags=["casino"])

_BOARD_SIZE = {"preflop": 0, "flop": 3, "turn": 4, "river": 5, "showdown": 5}
_BJ_TEXT = {
    "win": "Победа! Выигрыш {payout}",
    "natural": "Блэкджек! Выигрыш {payout}",
    "push": "Ничья — ставка {payout} возвращается.",
    "loss": "Дилер сильнее. Ставка проиграна.",
    "bust": "Перебор. Ставка проиграна.",
}


def _plain(text: str) -> str:
    return clean_label(text).replace("⭐", "★")


def _stake_error(exc: Exception) -> HTTPException:
    if isinstance(exc, CasinoBusyError):
        return bad(BUSY_ALERT)
    if isinstance(exc, X3StrategyError):
        return bad(X3_ALERT)
    if isinstance(exc, NotEnoughError):
        return bad(NOT_ENOUGH_ALERT)
    if isinstance(exc, HandInProgressError):
        return bad(HAND_IN_PROGRESS_ALERT)
    if isinstance(exc, HandNotFoundError):
        return bad(HAND_GONE_ALERT)
    return bad("Неверная ставка.")


# --- модели ---

class StakeIn(BaseModel):
    kind: Literal["res", "statist"]
    code: str = Field(min_length=1, max_length=64)
    amount: int = Field(gt=0)

    def stake(self) -> Stake:
        return Stake(self.kind, self.code, self.amount)


class ResourceOpt(BaseModel):
    code: str
    label: str
    balance: int


class SquadOpt(BaseModel):
    code: str
    label: str
    total: int


class SymbolOut(BaseModel):
    symbol: str
    multiplier: int


class CardOut(BaseModel):
    rank: str = ""
    suit: str = ""
    hidden: bool = False


class BlackjackOut(BaseModel):
    player: list[CardOut]
    dealer: list[CardOut]
    player_total: int
    dealer_total: int | None
    stake_label: str
    doubled: bool
    finished: bool
    can_double: bool
    outcome: str = ""
    payout: int = 0
    message: str = ""


class LobbyRow(BaseModel):
    id: int
    buy_in: int
    players: int
    max_players: int
    starts_in: int


class PokerConfig(BaseModel):
    buy_ins: list[int]
    max_players_min: int
    max_players_max: int
    wait_options: list[int]
    rake_percent: float
    action_timeout: int


class CasinoOut(BaseModel):
    resources: list[ResourceOpt]
    squads: list[SquadOpt]
    symbols: list[SymbolOut]
    pair_multiplier: float
    statists_min: int
    blackjack: BlackjackOut | None
    lobby: list[LobbyRow]
    seat_table_id: int | None
    poker: PokerConfig
    coins: int


def _card(c) -> CardOut:
    return CardOut(rank=str(c[0]), suit=str(c[1]))


def _bj(state: casino_svc.BlackjackState) -> BlackjackOut:
    dealer = [_card(c) for c in state.dealer]
    if not state.finished and len(dealer) > 1:
        dealer = [dealer[0], CardOut(hidden=True)]
    stake = state.stake
    label = _stake_label(stake)
    msg = ""
    if state.finished and state.outcome:
        msg = _BJ_TEXT[state.outcome].format(payout=format_number(state.payout))
    return BlackjackOut(
        player=[_card(c) for c in state.player], dealer=dealer, player_total=state.player_total,
        dealer_total=state.dealer_total if state.finished else casino_svc.hand_value(state.dealer[:1]),
        stake_label=label, doubled=state.doubled, finished=state.finished,
        can_double=(not state.finished) and len(state.player) == 2 and not state.doubled,
        outcome=state.outcome, payout=state.payout, message=msg,
    )


def _stake_label(stake: Stake) -> str:
    if stake.kind == STAKE_RESOURCE:
        return f"{format_number(stake.amount)} {RESOURCE_NAMES.get(stake.code, stake.code)}"
    return f"{format_number(stake.amount)} × {_plain(item_label(STAKE_STATIST, stake.code))}"


async def _squad_opts(session: AsyncSession, user_id: int) -> list[SquadOpt]:
    out = []
    for s in await list_squads(session, user_id):
        total = s.attack + s.defense
        if total <= 0:
            continue
        code = StatistKey(s.rank, s.stars, s.training_level, s.school, s.school_level).encode()
        out.append(SquadOpt(code=code, label=_plain(item_label(STAKE_STATIST, code)), total=total))
    return out


@router.get("", response_model=CasinoOut)
async def get_casino(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                     redis: Redis = Depends(get_redis)) -> CasinoOut:
    await require_user(session, user_id)
    bal = await balances(session, user_id)
    hand = await casino_svc.current_hand(redis, user_id)
    tables = await poker_svc.lobby(session)
    return CasinoOut(
        resources=[ResourceOpt(code=c, label=RESOURCE_NAMES.get(c, c), balance=bal.get(c, 0))
                   for c in RESOURCES if c not in NO_MINT_RESOURCES],
        squads=await _squad_opts(session, user_id),
        symbols=[SymbolOut(symbol=s, multiplier=m) for s, (_, m) in SLOTS_SYMBOLS.items()],
        pair_multiplier=SLOTS_PAIR_MULTIPLIER, statists_min=BLACKJACK_STATISTS_MIN,
        blackjack=_bj(hand) if hand else None,
        lobby=[LobbyRow(id=t.id, buy_in=t.buy_in, players=t.players, max_players=t.max_players, starts_in=t.starts_in) for t in tables],
        seat_table_id=await poker_svc.seat_of(session, user_id),
        poker=PokerConfig(
            buy_ins=list(POKER_BUY_INS), max_players_min=POKER_MIN_PLAYERS, max_players_max=POKER_MAX_PLAYERS,
            wait_options=list(POKER_WAIT_OPTIONS_SECONDS), rake_percent=POKER_RAKE_PERCENT,
            action_timeout=POKER_ACTION_TIMEOUT_SECONDS,
        ),
        coins=bal.get("coins", 0),
    )


# --- слоты ---

@router.post("/slots/spin")
async def spin(body: StakeIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
               redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    try:
        res = await casino_svc.play_slots(session, redis, user_id, body.stake())
    except (CasinoBusyError, X3StrategyError, NotEnoughError, InvalidStakeError) as exc:
        raise _stake_error(exc) from exc
    stake = _stake_label(res.stake)
    if res.outcome == casino_svc.OUTCOME_TRIPLE:
        message = f"Тройка! Ставка {stake} → выигрыш {format_number(res.payout)}"
    elif res.outcome == casino_svc.OUTCOME_PAIR:
        message = f"Пара — ставка {stake} возвращается."
    else:
        message = f"Мимо. Ставка {stake} проиграна."
    return {"message": message, "reel": list(res.reel), "outcome": res.outcome, "payout": res.payout}


# --- блэкджек ---

def _bj_action_result(state: casino_svc.BlackjackState) -> dict:
    out = _bj(state)
    return {"message": out.message or "Твой ход.", "hand": out.model_dump()}


@router.post("/blackjack/deal")
async def bj_deal(body: StakeIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                  redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    if body.kind == STAKE_STATIST and body.amount < BLACKJACK_STATISTS_MIN:
        raise bad(STATISTS_MIN_ALERT)
    try:
        state = await casino_svc.blackjack_deal(session, redis, user_id, body.stake())
    except (CasinoBusyError, X3StrategyError, NotEnoughError, InvalidStakeError, HandInProgressError) as exc:
        raise _stake_error(exc) from exc
    return _bj_action_result(state)


@router.post("/blackjack/{action}")
async def bj_action(action: Literal["hit", "stand", "double"], user_id: int = Depends(get_current_user_id),
                    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    fn = {"hit": casino_svc.blackjack_hit, "stand": casino_svc.blackjack_stand, "double": casino_svc.blackjack_double}[action]
    try:
        state = await fn(session, redis, user_id)
    except (CasinoBusyError, NotEnoughError, HandNotFoundError) as exc:
        raise _stake_error(exc) from exc
    return _bj_action_result(state)


# --- покер ---

def _pcard(c) -> CardOut:
    rank, suit = c
    return CardOut(rank=RANK_NAMES.get(rank, str(rank)), suit=SUITS[suit])


class PokerSeat(BaseModel):
    seat: int
    name: str
    stack: int
    round_bet: int
    folded: bool
    all_in: bool
    leaving: bool
    dealer: bool
    turn: bool
    me: bool


class PokerTableOut(BaseModel):
    id: int
    status: str  # waiting | active | closed
    hand_no: int
    street: str
    buy_in: int
    small_blind: int
    big_blind: int
    max_players: int
    pot: int
    starts_in: int
    board: list[CardOut]
    hole: list[CardOut]
    seats: list[PokerSeat]
    my_turn: bool
    to_call: int
    min_raise_to: int
    all_in_to: int
    can_raise: bool
    seconds_left: int


async def _gang_names(session: AsyncSession, ids: list[int]) -> dict[int, str]:
    rows = await session.execute(select(Gang.user_id, Gang.name).where(Gang.user_id.in_(ids)))
    return dict(rows.all())


@router.get("/poker/table/{table_id}", response_model=PokerTableOut)
async def poker_table(table_id: int, user_id: int = Depends(get_current_user_id),
                      session: AsyncSession = Depends(get_session)) -> PokerTableOut:
    await require_user(session, user_id)
    table, players = await poker_svc.get_table(session, table_id)
    me = next((p for p in players if p.user_id == user_id), None)
    if table is None or me is None or table.status not in (TABLE_WAITING, TABLE_ACTIVE):
        return PokerTableOut(
            id=table_id, status="closed", hand_no=0, street="", buy_in=0, small_blind=0, big_blind=0, max_players=0,
            pot=0, starts_in=0, board=[], hole=[], seats=[], my_turn=False, to_call=0, min_raise_to=0, all_in_to=0,
            can_raise=False, seconds_left=0,
        )
    now = datetime.now(timezone.utc)
    names = await _gang_names(session, [p.user_id for p in players])
    active = table.status == TABLE_ACTIVE
    dealer = table.dealer_seat % len(players) if active else -1
    seats = [
        PokerSeat(
            seat=p.seat, name=names.get(p.user_id, "—"), stack=p.stack, round_bet=p.round_bet,
            folded=p.status == PLAYER_FOLDED, all_in=p.status == PLAYER_ALL_IN, leaving=p.leaving,
            dealer=active and p.seat == dealer, turn=active and p.seat == table.current_seat, me=p.user_id == user_id,
        )
        for p in players
    ]
    my_turn = active and me.seat == table.current_seat and me.status == "active"
    call = poker_svc.to_call(table, me) if active else 0
    all_in = me.round_bet + me.stack
    return PokerTableOut(
        id=table.id, status=table.status, hand_no=table.hand_no, street=table.street if active else "",
        buy_in=table.buy_in, small_blind=table.small_blind, big_blind=table.big_blind, max_players=table.max_players,
        pot=table.pot if active else 0,
        starts_in=max(0, int((table.starts_at - now).total_seconds())) if table.status == TABLE_WAITING else 0,
        board=[_pcard(c) for c in json.loads(table.community)[:_BOARD_SIZE.get(table.street, 0)]] if active else [],
        hole=[_pcard(c) for c in json.loads(me.hole)] if active else [],
        seats=seats, my_turn=my_turn, to_call=min(call, me.stack),
        min_raise_to=poker_svc.min_raise_to(table, me) if active else 0, all_in_to=all_in,
        can_raise=active and all_in > table.current_bet,
        seconds_left=max(0, int((table.action_deadline - now).total_seconds())) if active and table.action_deadline else 0,
    )


class CreateTableIn(BaseModel):
    buy_in: int
    max_players: int
    wait: int


class TableIdIn(BaseModel):
    table_id: int


class ActIn(BaseModel):
    table_id: int
    hand_no: int
    action: Literal["fold", "check", "call", "raise"]
    amount: int = Field(0, ge=0)


def _perr(exc: PokerError) -> HTTPException:
    return bad(POKER_ERRORS.get(exc.code, "Не получилось."))


@router.post("/poker/create")
async def poker_create(body: CreateTableIn, user_id: int = Depends(get_current_user_id),
                       session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    try:
        ev = await poker_svc.create(session, user_id, body.buy_in, body.max_players, body.wait)
    except PokerError as exc:
        raise _perr(exc) from exc
    return {"message": "Стол создан — ждём игроков", "table_id": ev.table_id}


@router.post("/poker/join")
async def poker_join(body: TableIdIn, user_id: int = Depends(get_current_user_id),
                     session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    try:
        ev = await poker_svc.join(session, user_id, body.table_id)
    except PokerError as exc:
        raise _perr(exc) from exc
    await push_poker(ev, skip_user=user_id)
    return {"message": "Ты за столом", "table_id": ev.table_id}


@router.post("/poker/leave")
async def poker_leave(body: TableIdIn, user_id: int = Depends(get_current_user_id),
                      session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    try:
        ev = await poker_svc.leave(session, user_id, body.table_id)
    except PokerError as exc:
        raise _perr(exc) from exc
    if ev.kind == "left":
        await push_poker(PokerEvent(ev.table_id, "joined", []))
    else:
        await push_poker(PokerEvent(ev.table_id, "action", []))
    return {"message": "Встанешь после раздачи" if ev.kind == "leaving" else "Ты вышел из-за стола"}


@router.post("/poker/act")
async def poker_act(body: ActIn, user_id: int = Depends(get_current_user_id),
                    session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    if body.action not in (ACT_FOLD, ACT_CHECK, ACT_CALL, ACT_RAISE):
        raise bad("Неизвестное действие.")
    try:
        ev = await poker_svc.act(session, user_id, body.table_id, body.hand_no, body.action, body.amount)
    except PokerError as exc:
        raise _perr(exc) from exc
    await push_poker(ev, skip_user=user_id)
    message = "Ход принят"
    if ev.kind == "hand_finished" and ev.result:
        mine = next((p for p in ev.result["players"] if p["user_id"] == user_id), None)
        won = mine["won"] if mine else 0
        message = f"Раздача окончена: выигрыш {format_number(won)}" if won else "Раздача окончена"
    return {"message": message}
