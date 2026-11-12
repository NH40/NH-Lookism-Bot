"""«Пятницы» в Mini App: экран игрока и раздел админки. Логика — `services/sale` (как в боте)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session, session_factory
from api.deps import get_redis
from api.push import get_bot
from api.routers._common import bad, clean_label
from bot.constant.admin import SECTION_SALE
from bot.constant.sale import AUDIT_SALE_START, AUDIT_SALE_STOP, CATEGORIES, SALE_CHOSEN, SALE_KINDS, SALE_REBIRTH, SPECIAL_SALES
from bot.services import sale as svc
from bot.services.admin import audit
from bot.texts import sale as t

router = APIRouter(prefix="/api", tags=["sale"])


def _left(until: datetime) -> int:
    return max(0, int((until - datetime.now(timezone.utc)).total_seconds()))


class SaleOut(BaseModel):
    active: dict | None
    categories: list[dict]


@router.get("/sale", response_model=SaleOut)
async def get_sale(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> SaleOut:
    v = await svc.view(session, user_id)
    active = None
    if v.sale is not None:
        kind = v.sale.kind
        active = {
            "kind": kind, "title": clean_label(t.TITLES[kind]), "about": t.ABOUT[kind], "left_seconds": _left(v.sale.ends_at),
            "chosen": kind == SALE_CHOSEN, "choices": v.choices, "special": kind in SPECIAL_SALES,
            "price": svc.SPECIAL_PRICES.get(kind), "bought": v.bought,
        }
    return SaleOut(active=active, categories=[{"code": c, "name": t.CATEGORY_NAMES[c]} for c in CATEGORIES])


class PickIn(BaseModel):
    category: str


@router.post("/sale/pick")
async def post_pick(body: PickIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    try:
        chosen = await svc.toggle_choice(session, user_id, body.category)
    except svc.NoSaleError:
        raise bad(t.NONE_ALERT)
    except svc.TooManyChoicesError:
        raise bad(t.TOO_MANY_ALERT)
    return {"message": "Выбрано: " + (", ".join(t.CATEGORY_NAMES[c] for c in chosen) or "ничего")}


@router.post("/sale/buy")
async def post_buy(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    try:
        kind = await svc.buy_special(session, redis, user_id)
    except svc.SaleBusyError:
        raise bad(t.BUSY_ALERT)
    except svc.NoSaleError:
        raise bad(t.NONE_ALERT)
    except svc.AlreadyBoughtError:
        raise bad(t.ALREADY_ALERT)
    except svc.CannotBuyError:
        raise bad(t.CANNOT_ALERT)
    except svc.NotEnoughDonateError as exc:
        raise bad(t.NOT_ENOUGH_ALERT.format(price=exc.price, balance=exc.balance))
    return {"message": t.BOUGHT_ALERT.format(title=clean_label(t.TITLES[kind])) + (t.REBIRTH_DONE if kind == SALE_REBIRTH else "")}


# --- админ ---


@router.get("/admin/sale")
async def admin_get(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    from api.routers.admin import access

    await access(session, user_id, SECTION_SALE)
    sale = await svc.active(session)
    return {
        "active": {"kind": sale.kind, "title": clean_label(t.TITLES[sale.kind]), "left_seconds": _left(sale.ends_at)} if sale else None,
        "kinds": [{"code": k, "title": clean_label(t.TITLES[k]), "about": t.ABOUT[k]} for k in SALE_KINDS],
    }


class StartIn(BaseModel):
    kind: str


@router.post("/admin/sale/start")
async def admin_start(body: StartIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    from api.routers.admin import access, background
    from bot.handlers.sale.sale import push_start

    await access(session, user_id, SECTION_SALE)
    try:
        sale = await svc.start(session, body.kind, user_id)
    except svc.SaleActiveError:
        await session.rollback()
        raise bad(t.ADMIN_ACTIVE_ALERT)
    except svc.NoSaleError:
        raise bad("Неизвестная пятница.")
    await audit.log(session, user_id, AUDIT_SALE_START, None, {"kind": body.kind, "id": sale.id})
    await session.commit()
    background(push_start(get_bot(), session_factory, body.kind))
    return {"message": t.ADMIN_STARTED.format(title=clean_label(t.TITLES[body.kind]))}


@router.post("/admin/sale/stop")
async def admin_stop(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    from api.routers.admin import access

    await access(session, user_id, SECTION_SALE)
    sale = await svc.stop(session)
    if sale is not None:
        await audit.log(session, user_id, AUDIT_SALE_STOP, None, {"kind": sale.kind, "id": sale.id})
        await session.commit()
    return {"message": t.ADMIN_STOPPED}
