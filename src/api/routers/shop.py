"""API-роутер Mini App: магазин — контракты, зелья, ячейки хранения, вклады.

Только сервисы бота (`services.contract/potion/storage/deposit`) — те же, что вызывают
хендлеры; роутер валидирует вход, собирает экран одним GET и переводит исключения в 400.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad, clean_label, require_user
from bot.config.characteristic import extra_power_for_rank
from bot.config.contract import CONTRACT_MAX_QUANTITY
from bot.config.deposit import DEPOSIT_MAX_ACTIVE, DEPOSIT_RATES
from bot.config.potion import POTION_TIERS
from bot.config.storage import STORAGE_DEBT_CAP_HOURS, STORAGE_FEE_PER_HOUR
from bot.constant.potion import POTIONS
from bot.constant.resource import ITEM_RESOURCE, ITEM_STATIST, NO_MINT_RESOURCES, RESOURCES
from bot.services import contract as contract_svc
from bot.services import deposit as deposit_svc
from bot.services import potion as potion_svc
from bot.services import storage as storage_svc
from bot.services.business import get_wallet
from bot.services.extra import list_squads
from bot.services.resource import StatistKey, balances
from bot.texts.contract import BOUGHT_ALERT as CONTRACT_BOUGHT
from bot.texts.deposit import CLAIMED_ALERT, CLAIMED_EARLY_ALERT
from bot.texts.development.effects import describe_level
from bot.texts.potion import (
    AUTO_FULL_ALERT,
    AUTO_NO_SLOTS_ALERT,
    AUTO_OFF_ALERT,
    AUTO_ON_ALERT,
    DRANK_ALERT,
    LOCKED_ALERT,
    POTION_ABOUT,
    POTION_NAMES,
    ROMAN,
)
from bot.texts.resource import RESOURCE_NAMES, item_label
from bot.texts.storage import OPENED_ALERT, STORED, TAKEN, TAKEN_PAID
from bot.utils.formatting import format_number

router = APIRouter(prefix="/api/shop", tags=["shop"])

_BUSY = "Обрабатываю…"
_NOT_ENOUGH = "Столько нет."
_RANK_LOCKED = "Этот ранг выше твоего потолка по влиянию."


def _coins(cost: int) -> str:
    return f"Не хватает NHCoin: нужно {format_number(cost)}."


def _plain(text: str) -> str:
    return clean_label(text.replace("<b>", "").replace("</b>", ""))


# --- модели ---


class RankOut(BaseModel):
    rank: str
    unit_price: int
    power: int


class ContractActiveOut(BaseModel):
    rank: str
    quantity: int
    expires_in_seconds: int


class ContractsOut(BaseModel):
    ceiling: str
    hours: float
    discount: float
    max_quantity: int
    ranks: list[RankOut]  # от слабого к сильному, до потолка
    active: list[ContractActiveOut]


class TierOut(BaseModel):
    tier: int
    price: int
    unlocked: bool
    effect: str


class PotionOut(BaseModel):
    kind: str
    name: str
    about: str
    minutes: int
    tiers: list[TierOut]
    active_tier: int
    left_seconds: int
    auto_tier: int


class PotionsOut(BaseModel):
    max_tier: int
    auto_slots: int
    discount: float
    potions: list[PotionOut]


class CellOut(BaseModel):
    slot: int
    opened: bool
    kind: str  # "" | "res" | "statist"
    code: str
    label: str
    amount: int
    debt: int
    open_cost: int
    next_to_open: bool


class StoreResOut(BaseModel):
    code: str
    name: str
    have: int


class StoreSquadOut(BaseModel):
    code: str
    label: str
    have: int


class StorageOut(BaseModel):
    fee_per_hour: int
    debt_cap_hours: int
    cells: list[CellOut]
    resources: list[StoreResOut]
    squads: list[StoreSquadOut]


class DepositOut(BaseModel):
    id: int
    resource: str
    name: str
    amount: int
    payout: int
    rate: float
    hours: int
    left_seconds: int
    ready: bool


class DepositResOut(BaseModel):
    code: str
    name: str
    cap: int
    have: int
    rates: dict[int, float]


class DepositsOut(BaseModel):
    max_active: int
    terms: list[int]
    resources: list[DepositResOut]
    deposits: list[DepositOut]


class ShopOut(BaseModel):
    nh_coins: int
    pending: int
    contracts: ContractsOut
    potions: PotionsOut
    storage: StorageOut
    deposits: DepositsOut


class QuoteOut(BaseModel):
    rank: str
    quantity: int
    unit_price: int
    total: int
    hours: float
    power: int


class MsgOut(BaseModel):
    message: str


class BuyContractIn(BaseModel):
    rank: str
    quantity: int = Field(ge=1, le=CONTRACT_MAX_QUANTITY)


class PotionIn(BaseModel):
    kind: str
    tier: int = Field(ge=0, le=POTION_TIERS)


class SlotIn(BaseModel):
    slot: int = Field(ge=1, le=100)


class StoreIn(SlotIn):
    kind: Literal["res", "statist"]
    code: str = Field(max_length=64)
    amount: int = Field(ge=1)


class RetrieveIn(SlotIn):
    amount: int | None = Field(default=None, ge=1)


class OpenDepositIn(BaseModel):
    resource: str
    hours: int
    amount: int = Field(ge=1)


class ClaimDepositIn(BaseModel):
    id: int


# --- сборка экрана ---


async def _contracts(session: AsyncSession, user_id: int) -> ContractsOut:
    terms = await contract_svc.terms(session, user_id)
    ranks = [RankOut(rank=r, unit_price=terms.unit_price(r), power=extra_power_for_rank(r)) for r in reversed(terms.ranks)]
    active = await contract_svc.active(session, user_id)
    return ContractsOut(
        ceiling=terms.ceiling, hours=terms.hours, discount=terms.discount, max_quantity=CONTRACT_MAX_QUANTITY,
        ranks=ranks,
        active=[ContractActiveOut(rank=a.rank, quantity=a.quantity, expires_in_seconds=a.expires_in_seconds) for a in active],
    )


async def _potions(session: AsyncSession, user_id: int) -> PotionsOut:
    cat = await potion_svc.catalog(session, user_id)
    out = []
    for kind in POTIONS:
        offers = await potion_svc.offers(session, user_id, kind)
        state = cat.states.get(kind)
        out.append(PotionOut(
            kind=kind, name=clean_label(POTION_NAMES[kind]), about=POTION_ABOUT[kind], minutes=offers[0].minutes,
            tiers=[TierOut(tier=o.tier, price=o.price, unlocked=o.unlocked, effect=describe_level(o.spec)) for o in offers],
            active_tier=state.tier if state else 0, left_seconds=state.left_seconds if state else 0,
            auto_tier=state.auto_tier if state else 0,
        ))
    return PotionsOut(max_tier=cat.max_tier, auto_slots=cat.auto_slots, discount=cat.discount, potions=out)


async def _storage(session: AsyncSession, user_id: int, bal: dict[str, int]) -> StorageOut:
    cells = await storage_svc.cells(session, user_id)
    first_closed = next((c.slot for c in cells if not c.opened), None)
    squads = await list_squads(session, user_id)
    codes = [StatistKey(s.rank, s.stars, s.training_level, s.school, s.school_level).encode() for s in squads]
    return StorageOut(
        fee_per_hour=STORAGE_FEE_PER_HOUR, debt_cap_hours=STORAGE_DEBT_CAP_HOURS,
        cells=[
            CellOut(
                slot=c.slot, opened=c.opened, kind=c.kind, code=c.code,
                label=clean_label(item_label(c.kind, c.code)) if not c.empty else "",
                amount=c.amount, debt=c.debt, open_cost=c.open_cost, next_to_open=c.slot == first_closed,
            )
            for c in cells
        ],
        resources=[StoreResOut(code=r, name=RESOURCE_NAMES[r], have=bal.get(r, 0)) for r in RESOURCES],
        squads=[
            StoreSquadOut(code=code, label=clean_label(item_label(ITEM_STATIST, code)), have=s.total)
            for s, code in zip(squads, codes) if s.total > 0
        ],
    )


async def _deposits(session: AsyncSession, user_id: int, bal: dict[str, int]) -> DepositsOut:
    resources = []
    for code in RESOURCES:
        if code in NO_MINT_RESOURCES:
            continue
        resources.append(DepositResOut(
            code=code, name=RESOURCE_NAMES[code], cap=await deposit_svc.cap_for(session, user_id, code),
            have=bal.get(code, 0), rates={h: deposit_svc.rate_for(code, h) for h in DEPOSIT_RATES},
        ))
    views = await deposit_svc.list_deposits(session, user_id)
    return DepositsOut(
        max_active=DEPOSIT_MAX_ACTIVE, terms=list(DEPOSIT_RATES), resources=resources,
        deposits=[
            DepositOut(
                id=d.id, resource=d.resource, name=RESOURCE_NAMES.get(d.resource, d.resource), amount=d.amount,
                payout=d.payout, rate=d.rate, hours=d.hours, left_seconds=d.left_seconds, ready=d.ready,
            )
            for d in views
        ],
    )


@router.get("", response_model=ShopOut)
async def get_shop(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ShopOut:
    await require_user(session, user_id)
    wallet = await get_wallet(session, user_id)
    bal = await balances(session, user_id)
    return ShopOut(
        nh_coins=wallet.nh_coins if wallet else 0,
        pending=wallet.pending if wallet else 0,
        contracts=await _contracts(session, user_id),
        potions=await _potions(session, user_id),
        storage=await _storage(session, user_id, bal),
        deposits=await _deposits(session, user_id, bal),
    )


# --- контракты ---


@router.get("/quote", response_model=QuoteOut)
async def get_quote(
    rank: str,
    quantity: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> QuoteOut:
    await require_user(session, user_id)
    try:
        q = await contract_svc.quote(session, user_id, rank, quantity)
    except contract_svc.RankNotAvailableError:
        raise bad(_RANK_LOCKED)
    except contract_svc.InvalidQuantityError:
        raise bad(f"Нужно целое число от 1 до {format_number(CONTRACT_MAX_QUANTITY)}.")
    return QuoteOut(rank=q.rank, quantity=q.quantity, unit_price=q.unit_price, total=q.total, hours=q.hours, power=q.power)


@router.post("/contract/buy", response_model=MsgOut)
async def buy_contract(
    body: BuyContractIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> MsgOut:
    await require_user(session, user_id)
    try:
        q = await contract_svc.buy(session, redis, user_id, body.rank, body.quantity)
    except contract_svc.RankNotAvailableError:
        raise bad(_RANK_LOCKED)
    except contract_svc.InvalidQuantityError:
        raise bad("Некорректное количество.")
    except contract_svc.NotEnoughCoinsError as e:
        raise bad(_coins(e.cost))
    except contract_svc.ShopBusyError:
        raise bad(_BUSY)
    return MsgOut(message=CONTRACT_BOUGHT.format(quantity=format_number(q.quantity), rank=q.rank, hours=f"{q.hours:g}"))


# --- зелья ---


@router.post("/potion/buy", response_model=MsgOut)
async def buy_potion(
    body: PotionIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> MsgOut:
    await require_user(session, user_id)
    try:
        offer = await potion_svc.buy(session, redis, user_id, body.kind, body.tier)
    except potion_svc.UnknownPotionError:
        raise bad("Неизвестное зелье.")
    except potion_svc.TierLockedError as e:
        raise bad(LOCKED_ALERT.format(roman=ROMAN[e.max_tier]))
    except potion_svc.NotEnoughCoinsError as e:
        raise bad(_coins(e.cost))
    except potion_svc.PotionBusyError:
        raise bad(_BUSY)
    name = clean_label(POTION_NAMES[offer.kind])
    return MsgOut(message=DRANK_ALERT.format(name=name, roman=ROMAN[offer.tier], minutes=offer.minutes))


@router.post("/potion/auto", response_model=MsgOut)
async def set_potion_auto(
    body: PotionIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> MsgOut:
    await require_user(session, user_id)
    if body.tier and (await potion_svc.catalog(session, user_id)).auto_slots <= 0:
        raise bad(AUTO_NO_SLOTS_ALERT)
    try:
        await potion_svc.set_auto(session, user_id, body.kind, body.tier)
    except potion_svc.UnknownPotionError:
        raise bad("Неизвестное зелье.")
    except potion_svc.TierLockedError as e:
        raise bad(LOCKED_ALERT.format(roman=ROMAN[e.max_tier]))
    except potion_svc.AutoSlotsFullError as e:
        raise bad(AUTO_FULL_ALERT.format(slots=e.slots))
    if not body.tier:
        return MsgOut(message=AUTO_OFF_ALERT)
    return MsgOut(message=AUTO_ON_ALERT.format(name=clean_label(POTION_NAMES[body.kind]), roman=ROMAN[body.tier]))


# --- ячейки ---

_STORAGE_ERRORS = (
    storage_svc.CellLockedError, storage_svc.CellOccupiedError, storage_svc.CellEmptyError,
    storage_svc.NotEnoughError, storage_svc.NotEnoughCoinsError, storage_svc.InvalidAmountError,
    storage_svc.StorageBusyError,
)


def _storage_error(e: Exception):
    if isinstance(e, storage_svc.CellLockedError):
        return bad("Эта ячейка ещё закрыта — открывай по порядку.")
    if isinstance(e, storage_svc.CellOccupiedError):
        return bad("В ячейке лежит другая вещь — сначала достань её.")
    if isinstance(e, storage_svc.CellEmptyError):
        return bad("Ячейка пуста.")
    if isinstance(e, storage_svc.NotEnoughError):
        return bad(_NOT_ENOUGH)
    if isinstance(e, storage_svc.NotEnoughCoinsError):
        return bad(_coins(e.cost))
    if isinstance(e, storage_svc.InvalidAmountError):
        return bad("Некорректное количество.")
    return bad(_BUSY)


@router.post("/storage/open", response_model=MsgOut)
async def open_cell(
    body: SlotIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> MsgOut:
    await require_user(session, user_id)
    try:
        cost = await storage_svc.open_cell(session, redis, user_id, body.slot)
    except _STORAGE_ERRORS as e:
        raise _storage_error(e)
    return MsgOut(message=OPENED_ALERT.format(n=body.slot, cost=format_number(cost)))


@router.post("/storage/store", response_model=MsgOut)
async def store(
    body: StoreIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> MsgOut:
    await require_user(session, user_id)
    key = None
    if body.kind == ITEM_STATIST:
        try:
            key = StatistKey.decode(body.code)
        except ValueError:
            raise bad("Некорректный отряд.")
    try:
        if key is None:
            total = await storage_svc.store_resource(session, redis, user_id, body.slot, body.code, body.amount)
        else:
            total = await storage_svc.store_statists(session, redis, user_id, body.slot, key, body.amount)
    except _STORAGE_ERRORS as e:
        raise _storage_error(e)
    item = clean_label(item_label(ITEM_RESOURCE if key is None else ITEM_STATIST, body.code))
    return MsgOut(message=_plain(STORED.format(n=body.slot, item=item, amount=format_number(total))))


@router.post("/storage/retrieve", response_model=MsgOut)
async def retrieve(
    body: RetrieveIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> MsgOut:
    await require_user(session, user_id)
    cell = next((c for c in await storage_svc.cells(session, user_id) if c.slot == body.slot), None)
    item = clean_label(item_label(cell.kind, cell.code)) if cell and not cell.empty else ""
    try:
        taken, paid = await storage_svc.retrieve(session, redis, user_id, body.slot, body.amount)
    except _STORAGE_ERRORS as e:
        raise _storage_error(e)
    fee = TAKEN_PAID.format(debt=format_number(paid)) if paid else ""
    return MsgOut(message=_plain(TAKEN.format(item=item, amount=format_number(taken), paid=fee)))


# --- вклады ---


@router.post("/deposit/open", response_model=MsgOut)
async def open_deposit(
    body: OpenDepositIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> MsgOut:
    await require_user(session, user_id)
    try:
        view = await deposit_svc.open_deposit(session, redis, user_id, body.resource, body.hours, body.amount)
    except deposit_svc.InvalidTermError:
        raise bad("Некорректный срок или ресурс.")
    except deposit_svc.InvalidAmountError as e:
        raise bad(f"Нужно число от 1 до {format_number(e.cap)}.")
    except deposit_svc.TooManyDepositsError:
        raise bad(f"Уже {DEPOSIT_MAX_ACTIVE} вклада — забери какой-нибудь.")
    except deposit_svc.NotEnoughError:
        raise bad(_NOT_ENOUGH)
    except deposit_svc.DepositBusyError:
        raise bad(_BUSY)
    return MsgOut(
        message=f"Вклад #{view.id} открыт: {format_number(view.amount)} на {view.hours} ч, заберёшь {format_number(view.payout)}."
    )


@router.post("/deposit/claim", response_model=MsgOut)
async def claim_deposit(
    body: ClaimDepositIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> MsgOut:
    await require_user(session, user_id)
    try:
        payout, matured = await deposit_svc.claim(session, redis, user_id, body.id)
    except deposit_svc.DepositNotFoundError:
        raise bad("Вклад уже забран.")
    except deposit_svc.DepositBusyError:
        raise bad(_BUSY)
    return MsgOut(message=(CLAIMED_ALERT if matured else CLAIMED_EARLY_ALERT).format(amount=format_number(payout)))
