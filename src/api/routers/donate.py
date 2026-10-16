"""API-роутер Mini App: пополнение донат-коинов и чёрный рынок.

Зачисление платежа делает хендлер `successful_payment` БОТА (тот же путь, что и при оплате из
чата) — здесь только создаётся ссылка на инвойс, которую Mini App открывает через
`WebApp.openInvoice`. Покупки рынка — через bot.services.donate (атомарно, с Redis-локом)."""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import LabeledPrice
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers.profile import plain
from bot.config.development import MAX_LEVEL
from bot.config.donate import DONATE_MAX_RUB, DONATE_MIN_RUB, DONATE_PRESETS_RUB
from bot.config.settings import get_settings
from bot.constant.donate import DONATE_KINDS, PAYLOAD_DONATE_PREFIX
from bot.db.repositories import donate as donate_repo
from bot.services import donate as donate_service
from bot.services.admin.live_config import get as live_get
from bot.services.battle_pass import get_page as get_battle_pass_page
from bot.services.donate import (
    AlreadyBoughtError,
    DonateBusyError,
    MaxLevelError,
    NotEnoughDonateError,
    NotUnlockedError,
    UnknownItemError,
)
from bot.texts.donate import (
    ALREADY_ALERT,
    BODY_BOUGHT_ALERT,
    BOUGHT_ALERT,
    BTN_KIND,
    BUSY_ALERT,
    INVOICE_DESCRIPTION,
    INVOICE_LABEL,
    INVOICE_TITLE,
    ITEM_HINT,
    MAX_ALERT,
    NOT_ENOUGH_ALERT,
    NOT_UNLOCKED_ALERT,
)
from bot.texts.genius import GENIUS_NAMES
from bot.texts.unique_path import PATH_NAMES
from bot.texts.unique_technique import TECHNIQUE_NAMES
from bot.utils.formatting import format_number

router = APIRouter(prefix="/api/donate", tags=["donate"])

_KOPECKS_PER_RUB = 100
_NAMES = {"genius": GENIUS_NAMES, "path": PATH_NAMES, "tech": TECHNIQUE_NAMES}


class DonateOut(BaseModel):
    balance: int
    presets: list[int]
    min_rub: int
    max_rub: int
    payments_enabled: bool


class InvoiceIn(BaseModel):
    amount: int


@router.get("", response_model=DonateOut)
async def get_donate(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> DonateOut:
    return DonateOut(
        balance=await donate_service.balance(session, user_id),
        presets=list(DONATE_PRESETS_RUB),
        min_rub=DONATE_MIN_RUB,
        max_rub=DONATE_MAX_RUB,
        payments_enabled=bool(get_settings().yookassa_provider_token),
    )


@router.post("/invoice")
async def create_invoice(body: InvoiceIn, user_id: int = Depends(get_current_user_id)) -> dict:
    settings = get_settings()
    if not settings.yookassa_provider_token:
        raise HTTPException(400, "Оплата пока не подключена.")
    if not DONATE_MIN_RUB <= body.amount <= DONATE_MAX_RUB:
        raise HTTPException(400, f"Сумма — от {DONATE_MIN_RUB} до {format_number(DONATE_MAX_RUB)} ₽.")
    bot = Bot(settings.bot_token)
    try:
        link = await bot.create_invoice_link(
            title=INVOICE_TITLE,
            description=INVOICE_DESCRIPTION.format(amount=body.amount),
            payload=f"{PAYLOAD_DONATE_PREFIX}{body.amount}",
            provider_token=settings.yookassa_provider_token,
            currency="RUB",
            prices=[LabeledPrice(label=INVOICE_LABEL.format(amount=body.amount), amount=body.amount * _KOPECKS_PER_RUB)],
        )
    finally:
        await bot.session.close()
    return {"link": link, "message": ""}


# --- чёрный рынок ---


class MarketItemOut(BaseModel):
    code: str
    name: str
    level: int  # купленный уровень, 0 — не открыто
    next_price: int | None  # None — максимум
    owned_now: bool = False


class MarketKindOut(BaseModel):
    kind: str
    label: str
    hint: str
    items: list[MarketItemOut]


class MarketOut(BaseModel):
    balance: int
    max_level: int
    second_body_owned: bool
    second_body_price: int
    battle_pass_premium: bool
    battle_pass_price: int
    kinds: list[MarketKindOut]


@router.get("/market", response_model=MarketOut)
async def get_market(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> MarketOut:
    body = await donate_repo.body_state(session, user_id)
    page = await get_battle_pass_page(session, user_id)
    kinds = []
    for kind in DONATE_KINDS:
        items = await donate_service.market(session, user_id, kind)
        kinds.append(
            MarketKindOut(
                kind=kind,
                label=plain(BTN_KIND[kind]),
                hint=ITEM_HINT[kind],
                items=[
                    MarketItemOut(
                        code=i.code, name=_NAMES[kind].get(i.code, i.code), level=i.level, next_price=i.next_price
                    )
                    for i in items
                ],
            )
        )
    return MarketOut(
        balance=await donate_service.balance(session, user_id),
        max_level=MAX_LEVEL,
        second_body_owned=bool(body and body[0]),
        second_body_price=live_get("second_body_price"),
        battle_pass_premium=page.is_premium,
        battle_pass_price=live_get("bp_premium_price"),
        kinds=kinds,
    )


class BuyIn(BaseModel):
    kind: str
    code: str


def _buy_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DonateBusyError):
        return HTTPException(400, BUSY_ALERT)
    if isinstance(exc, NotEnoughDonateError):
        return HTTPException(
            400, NOT_ENOUGH_ALERT.format(price=format_number(exc.price), balance=format_number(exc.balance))
        )
    texts = {AlreadyBoughtError: ALREADY_ALERT, NotUnlockedError: NOT_UNLOCKED_ALERT, MaxLevelError: MAX_ALERT}
    return HTTPException(400, texts.get(type(exc), ALREADY_ALERT))


_BUY_ERRORS = (DonateBusyError, NotEnoughDonateError, AlreadyBoughtError, NotUnlockedError, MaxLevelError, UnknownItemError)


@router.post("/market/body")
async def buy_body(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    try:
        await donate_service.buy_second_body(session, redis, user_id)
    except _BUY_ERRORS as exc:
        raise _buy_error(exc)
    return {"message": BODY_BOUGHT_ALERT}


@router.post("/market/unlock")
async def buy_unlock(
    body: BuyIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    try:
        await donate_service.buy_unlock(session, redis, user_id, body.kind, body.code)
    except _BUY_ERRORS as exc:
        raise _buy_error(exc)
    return {"message": BOUGHT_ALERT}


@router.post("/market/level")
async def buy_level(
    body: BuyIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    try:
        await donate_service.buy_level(session, redis, user_id, body.kind, body.code)
    except _BUY_ERRORS as exc:
        raise _buy_error(exc)
    return {"message": BOUGHT_ALERT}
