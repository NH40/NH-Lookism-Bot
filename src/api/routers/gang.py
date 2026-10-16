"""API-роутер Mini App: банда — лагеря атаки/защиты, отряды, перевод между лагерями, вербовка.

Тот же сервисный код, что `bot.handlers.gang` (`services.extra.get_army_stats/list_squads/
move_between_camps`). Вербовка статистов и крутка уника — в `recruit.py` / `gacha.py`; здесь
их состояние (КД, тикеты) отдаётся в ответе экрана одним запросом.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad, clean_label, require_user, ttl_seconds
from bot.cache.keys import recruit_extra_cooldown
from bot.config.game import GANG_CAMP_MOVE_PERCENTS
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
from bot.services.district import get_influence
from bot.constant.extra import CONTRACT_SQUAD
from bot.services.extra import InvalidCampMoveError, get_army_stats, list_army_squads, move_between_camps
from bot.services.gang import get_gang
from bot.services.recruit import recruit_ceiling_rank
from bot.services.ticket import get_status
from bot.texts.gang import CAMP_NOTHING_TO_MOVE
from bot.texts.school import SCHOOL_NAMES

router = APIRouter(prefix="/api/gang", tags=["gang"])


class CampOut(BaseModel):
    quantity: int
    power: int


class SquadOut(BaseModel):
    rank: str
    stars: int
    training_level: int
    school: str | None
    school_level: int
    unit_power: int
    attack: int
    defense: int
    total: int


class TicketsOut(BaseModel):
    count: int
    cap: int
    next_in_seconds: int | None


class GangOut(BaseModel):
    name: str
    phase: str
    attack: CampOut
    defense: CampOut
    cards_quantity: int
    squads: list[SquadOut]
    move_percents: list[int]
    recruit_cooldown_seconds: int
    recruit_ceiling_rank: str
    tickets: TicketsOut


class MoveIn(BaseModel):
    from_camp: str
    percent: int = Field(ge=1, le=100)


class MoveOut(BaseModel):
    message: str
    moved: int


@router.get("", response_model=GangOut)
async def get_my_gang(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> GangOut:
    user = await require_user(session, user_id)
    gang = await get_gang(session, user.id)
    if gang is None:
        raise bad("Сначала пройди регистрацию в боте — набери /start.")
    army = await get_army_stats(session, user.id)
    squads = await list_army_squads(session, user.id)
    tickets = await get_status(session, user.id)
    influence = await get_influence(session, user.id)
    return GangOut(
        name=gang.name,
        phase=user.phase,
        attack=CampOut(quantity=army.attack.quantity, power=army.attack.power),
        defense=CampOut(quantity=army.defense.quantity, power=army.defense.power),
        cards_quantity=army.cards_quantity,
        squads=[
            SquadOut(
                rank=sq.rank, stars=sq.stars, training_level=sq.training_level,
                school="Контракт" if sq.school == CONTRACT_SQUAD else clean_label(SCHOOL_NAMES.get(sq.school, sq.school)) if sq.school else None,
                school_level=sq.school_level, unit_power=sq.unit_power, attack=sq.attack,
                defense=sq.defense, total=sq.total,
            )
            for sq in squads
        ],
        move_percents=list(GANG_CAMP_MOVE_PERCENTS),
        recruit_cooldown_seconds=await ttl_seconds(redis, recruit_extra_cooldown(user.id)),
        recruit_ceiling_rank=recruit_ceiling_rank(user.phase, influence),
        tickets=TicketsOut(count=tickets.count, cap=tickets.cap, next_in_seconds=tickets.next_in_seconds),
    )


@router.post("/move", response_model=MoveOut)
async def move_camps(
    body: MoveIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> MoveOut:
    """Перевод `percent`% каждой стопки лагеря `from_camp` в противоположный (CB_GANG_CAMP_MOVE)."""
    user = await require_user(session, user_id)
    if body.from_camp not in (CAMP_ATTACK, CAMP_DEFENSE):
        raise bad("Неизвестный лагерь.")
    to_camp = CAMP_DEFENSE if body.from_camp == CAMP_ATTACK else CAMP_ATTACK
    try:
        moved = await move_between_camps(session, user.id, body.from_camp, to_camp, body.percent)
    except InvalidCampMoveError:
        raise bad("Некорректный перевод.")
    if not moved:
        raise bad(clean_label(CAMP_NOTHING_TO_MOVE))
    where = "в защиту" if to_camp == CAMP_DEFENSE else "в атаку"
    return MoveOut(message=f"Переведено {where}: {moved:,}".replace(",", " "), moved=moved)


# --- Удаление банды (как в боте: запрос → подтверждение в течение N секунд, `services/gang.reset`) ---


class DeleteAskOut(BaseModel):
    seconds: int


@router.post("/delete/request", response_model=DeleteAskOut)
async def delete_request(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> DeleteAskOut:
    from bot.services.gang import request_delete

    if await get_gang(session, user_id) is None:
        raise bad("Банды нет.")
    return DeleteAskOut(seconds=await request_delete(redis, user_id))


class DeleteOut(BaseModel):
    message: str


@router.post("/delete/confirm", response_model=DeleteOut)
async def delete_confirm(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> DeleteOut:
    from api.push import with_bot_session
    from bot.keyboards.start import country_menu
    from bot.services.gang import ConfirmExpiredError, confirm_delete
    from bot.texts.gang import DELETE_DONE, DELETE_EXPIRED  # noqa: F401
    from bot.texts.start import CHOOSE_COUNTRY

    try:
        await confirm_delete(session, redis, user_id)
    except ConfirmExpiredError:
        raise bad(DELETE_EXPIRED)
    # Заново онбординг — в чате бота тот же первый экран, что у /start нового игрока.
    async def _onboard(bot, _session):
        await bot.send_message(user_id, DELETE_DONE)
        await bot.send_message(user_id, CHOOSE_COUNTRY, reply_markup=country_menu())

    await with_bot_session(_onboard)
    return DeleteOut(message="Банда удалена. Выбери страну в чате с ботом — меню уже там.")
