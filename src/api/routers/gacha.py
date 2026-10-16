"""API-роутер Mini App: крутка уника за тикет (`services.gacha.roll`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers._common import clean_label
from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad, require_user
from bot.constant.absolute import ABSOLUTES
from bot.services.position_skill import card_skill_lines
from bot.texts.absolute import PERKS
from bot.texts.card import POSITION_LABELS
from bot.texts.position_skill import KIND_LABELS
from bot.services.gacha import NoTicketsError, RollBusyError, roll
from bot.texts.card import RARITY_LABELS
from bot.utils.formatting import format_countdown

router = APIRouter(prefix="/api/gacha", tags=["gacha"])


class RolledCardOut(BaseModel):
    code: str
    name: str
    rarity: str
    rarity_label: str
    power: int
    image: str | None


class RolledSkillsOut(BaseModel):
    position: str
    label: str
    skills: list[dict]  # {name, kind_label, text}


class RollOut(BaseModel):
    message: str
    card: RolledCardOut
    skills: list[RolledSkillsOut] = []  # навыки по позициям (с числами редкости)
    absolute_perk: str | None = None
    copies: int
    free: bool
    tickets: int
    tickets_cap: int


@router.post("/roll", response_model=RollOut)
async def gacha_roll(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> RollOut:
    user = await require_user(session, user_id, need_city=False)
    try:
        result = await roll(session, redis, user.id)
    except RollBusyError:
        raise bad("Предыдущая крутка ещё обрабатывается.")
    except NoTicketsError as exc:
        wait = exc.status.next_in_seconds
        raise bad("Тикетов нет." + (f" Следующий через {format_countdown(wait)}." if wait else ""))
    card = result.card
    label = RARITY_LABELS.get(card.rarity, card.rarity)
    return RollOut(
        message=f"{card.name} — {label}" + (" (тикет вернулся)" if result.free else ""),
        card=RolledCardOut(
            code=card.code, name=card.name, rarity=card.rarity, rarity_label=label,
            power=card.power, image=card.image,
        ),
        skills=[
            RolledSkillsOut(position=p, label=clean_label(POSITION_LABELS[p]),
                            skills=[{"name": x.name, "kind_label": KIND_LABELS[x.kind], "text": x.text} for x in card_skill_lines(card, p)])
            for p in card.positions
        ],
        absolute_perk=PERKS.get(card.code) if card.code in ABSOLUTES else None,
        copies=result.copies, free=result.free,
        tickets=result.tickets.count, tickets_cap=result.tickets.cap,
    )
