"""Империя в Mini App — налоги, персональные ставки, война императоров (для императора) и
саботаж (для игрока в городе императора). Вся логика — сервисы бота `services/empire`, тексты
ошибок — те же алерты, что у бота (без HTML), пуши второй стороне — через `api.push`."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.push import push, with_bot_session
from api.routers._common import bad, clean_label, require_user, ttl_seconds
from api.routers.profile import plain
from bot.cache.keys import empire_war_cooldown, empire_war_shield
from bot.config.country import COUNTRY_BY_CODE
from bot.config.empire import (
    EMPIRE_TAX_MAX_PERCENT,
    EMPIRE_TAX_MIN_PERCENT,
    SABOTAGE_CHANCE_PERCENT,
    SABOTAGE_RECENT_HOURS,
)
from bot.constant.empire import SABOTAGE_ACTIONS, WAR_ACCEPTED, WAR_FORFEIT, WAR_VOID
from bot.constant.phase import PHASE_FIST
from bot.constant.settings import NOTIFY_SABOTAGE, NOTIFY_WAR_CALL
from bot.db.models.business import Business
from bot.db.repositories.empire import get_emperor as get_emperor_row
from bot.db.repositories.user import get_by_id
from bot.services.city import get_city
from bot.services.gang import get_gang
from bot.keyboards.empire import war_accept_menu
from bot.services.district import NoAttackersError
from bot.services.empire import (
    InvalidRateError,
    NoEmperorError,
    NotEmperorError,
    NotMarkedTargetError,
    NothingToStealError,
    OutgoingWarExistsError,
    SabotageOnCooldownError,
    SubjectNotFoundError,
    TargetAtWarError,
    TargetHasNoCitiesError,
    TargetNotEmperorError,
    TargetShieldedError,
    UnknownSabotageError,
    WarNotEmperorError,
    WarNotFoundError,
    WarOnCooldownError,
    accept_war,
    declare_war,
    find_subject,
    get_incoming_war,
    get_overview,
    get_sabotage_view,
    list_war_targets,
    sabotage,
    set_global_rate,
    set_personal_rate,
    war_history,
)
from bot.texts.district import NO_ATTACKERS
from bot.texts.empire import (
    INVALID_RATE_ALERT,
    NO_EMPEROR,
    NOT_EMPEROR_ALERT,
    NOT_MARKED_ALERT,
    NOTHING_TO_STEAL_ALERT,
    OUTGOING_WAR_EXISTS_ALERT,
    PERSONAL_RESET_ALERT,
    PERSONAL_SET_ALERT,
    PUSH_SABOTAGE_FAIL,
    PUSH_SABOTAGE_SUCCESS,
    PUSH_WAR_DECLARED,
    RATE_SET_ALERT,
    SABOTAGE_COOLDOWN_ALERT,
    SABOTAGE_FAIL,
    SABOTAGE_LABELS,
    SABOTAGE_SUCCESS,
    SUBJECT_NOT_FOUND,
    TARGET_AT_WAR_ALERT,
    TARGET_NO_CITIES_ALERT,
    TARGET_NOT_EMPEROR_ALERT,
    TARGET_SHIELDED_ALERT,
    WAR_COOLDOWN_ALERT,
    WAR_DECLARED,
    WAR_NOT_EMPEROR_ALERT,
    WAR_NOT_FOUND_ALERT,
)
from bot.utils.formatting import esc, format_countdown

router = APIRouter(prefix="/api/empire", tags=["empire"])


def _name(username: str | None, display_name: str | None) -> str:
    return display_name or (f"@{username}" if username else "Император")


class OverrideOut(BaseModel):
    username: str | None
    name: str
    percent: int


class IncomingWarOut(BaseModel):
    war_id: int
    attacker: str
    expires_in_seconds: int


class WarHistoryOut(BaseModel):
    war_id: int
    as_attacker: bool
    other: str
    won: bool | None  # None — война аннулирована
    forfeit: bool  # защитник не принял вызов
    cities: int
    treasury: int


class RulerOut(BaseModel):
    cities: int
    players: int
    tax_percent: int
    collected: int
    treasury: int
    holdings: int
    overrides: list[OverrideOut]
    overrides_total: int
    sabotage_total: int
    sabotage_success: int
    sabotage_hours: int
    incoming: IncomingWarOut | None
    war_cooldown_seconds: int
    history: list[WarHistoryOut]


class SabotageActionOut(BaseModel):
    code: str
    label: str
    chance: int
    cooldown_seconds: int


class SubjectOut(BaseModel):
    emperor: str
    emperor_username: str | None
    emperor_cities: int
    emperor_country: str | None
    tax_percent: int
    actions: list[SabotageActionOut]


class EmpireOut(BaseModel):
    ruler: RulerOut | None  # игрок сам император
    subject: SubjectOut | None  # над городом игрока есть император (может быть и у императора)
    tax_min: int
    tax_max: int
    subtitle: str  # «НХ · Россия» императору, «твой город — Воронеж» подданному


async def _ruler(session: AsyncSession, redis: Redis, user_id: int) -> RulerOut:
    stats = await get_overview(session, user_id)
    holdings = int(await session.scalar(select(func.count(Business.id)).where(Business.holder_id == user_id)) or 0)
    incoming = None
    war = await get_incoming_war(session, user_id)
    if war is not None:
        attacker = await get_by_id(session, war.attacker_id)
        left = int((war.expires_at - datetime.now(timezone.utc)).total_seconds())
        incoming = IncomingWarOut(
            war_id=war.id, attacker=_name(attacker.username if attacker else None, attacker.display_name if attacker else None),
            expires_in_seconds=max(0, left),
        )
    history = [
        WarHistoryOut(
            war_id=h.war_id, as_attacker=h.as_attacker, other=_name(h.other_username, h.other_display_name),
            won=None if h.resolution == WAR_VOID else bool(h.attacker_won) == h.as_attacker,
            forfeit=h.resolution == WAR_FORFEIT, cities=h.cities_taken, treasury=h.treasury_taken,
        )
        for h in await war_history(session, user_id)
    ]
    return RulerOut(
        cities=stats.cities, players=stats.players, tax_percent=stats.tax_percent, collected=stats.collected,
        treasury=stats.nh_coins, holdings=holdings,
        overrides=[OverrideOut(username=u, name=_name(u, n), percent=p) for u, n, p in stats.overrides],
        overrides_total=stats.overrides_total, sabotage_total=stats.sabotage_total,
        sabotage_success=stats.sabotage_success, sabotage_hours=SABOTAGE_RECENT_HOURS, incoming=incoming,
        war_cooldown_seconds=await ttl_seconds(redis, empire_war_cooldown(user_id)), history=history,
    )


async def _subject(session: AsyncSession, redis: Redis, user_id: int) -> SubjectOut | None:
    try:
        view = await get_sabotage_view(session, redis, user_id)
    except NoEmperorError:
        return None
    e = view.emperor
    row = await get_emperor_row(session, e.emperor_id)
    return SubjectOut(
        emperor=e.emperor_name or (f"@{e.emperor_username}" if e.emperor_username else "Император"),
        emperor_username=e.emperor_username, emperor_cities=row.cities if row else 0,
        emperor_country=clean_label(row.country_name) if row and row.country_name else None, tax_percent=e.percent,
        actions=[
            SabotageActionOut(code=a, label=plain(SABOTAGE_LABELS[a]), chance=SABOTAGE_CHANCE_PERCENT[a], cooldown_seconds=view.cooldowns[a])
            for a in SABOTAGE_ACTIONS
        ],
    )


@router.get("", response_model=EmpireOut)
async def get_empire(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> EmpireOut:
    user = await require_user(session, user_id)
    ruler = await _ruler(session, redis, user_id) if user.phase == PHASE_FIST else None
    if ruler is not None:
        country = COUNTRY_BY_CODE.get(user.country_code)
        gang = await get_gang(session, user_id)
        subtitle = " · ".join(x for x in (user.display_name or (gang.name if gang else None), clean_label(country.name) if country else None) if x)
    else:
        city = await get_city(session, user.city_id)
        subtitle = f"твой город — {city.name}" if city else ""
    return EmpireOut(
        ruler=ruler, subject=await _subject(session, redis, user_id),
        tax_min=EMPIRE_TAX_MIN_PERCENT, tax_max=EMPIRE_TAX_MAX_PERCENT, subtitle=subtitle,
    )


class MessageOut(BaseModel):
    message: str


class TaxIn(BaseModel):
    percent: int


@router.post("/tax", response_model=MessageOut)
async def post_tax(
    body: TaxIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> MessageOut:
    try:
        await set_global_rate(session, user_id, body.percent)
    except NotEmperorError:
        raise bad(NOT_EMPEROR_ALERT)
    except InvalidRateError:
        raise bad(INVALID_RATE_ALERT)
    return MessageOut(message=RATE_SET_ALERT.format(percent=body.percent))


class SubjectRateOut(BaseModel):
    user_id: int
    name: str
    percent: int
    own: bool  # персональная ставка (иначе — общая)


@router.get("/subject", response_model=SubjectRateOut)
async def get_subject(
    username: str = Query(..., min_length=1, max_length=64),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> SubjectRateOut:
    try:
        found = await find_subject(session, user_id, username.strip().lstrip("@"))
    except NotEmperorError:
        raise bad(NOT_EMPEROR_ALERT)
    except SubjectNotFoundError:
        raise bad(clean_label(SUBJECT_NOT_FOUND).split(".")[0] + ".")
    s = found.subject
    return SubjectRateOut(user_id=s.user_id, name=_name(s.username, s.display_name), percent=found.percent, own=found.has_override)


class PersonalIn(BaseModel):
    user_id: int
    percent: int | None  # None — снять, действует общий налог


@router.post("/personal", response_model=MessageOut)
async def post_personal(
    body: PersonalIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> MessageOut:
    try:
        await set_personal_rate(session, user_id, body.user_id, body.percent)
    except NotEmperorError:
        raise bad(NOT_EMPEROR_ALERT)
    except InvalidRateError:
        raise bad(INVALID_RATE_ALERT)
    except SubjectNotFoundError:
        raise bad(clean_label(SUBJECT_NOT_FOUND).split(".")[0] + ".")
    if body.percent is None:
        return MessageOut(message=PERSONAL_RESET_ALERT)
    return MessageOut(message=PERSONAL_SET_ALERT.format(percent=body.percent))


class WarTargetOut(BaseModel):
    user_id: int
    name: str
    country: str | None
    cities: int
    treasury: int
    shield_seconds: int


class WarTargetsOut(BaseModel):
    items: list[WarTargetOut]
    page: int
    has_more: bool


@router.get("/war/targets", response_model=WarTargetsOut)
async def get_war_targets(
    page: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> WarTargetsOut:
    try:
        result = await list_war_targets(session, user_id, page)
    except WarNotEmperorError:
        raise bad(WAR_NOT_EMPEROR_ALERT)
    items = [
        WarTargetOut(
            user_id=t.user_id, name=_name(t.username, t.display_name), country=t.country_name and clean_label(t.country_name),
            cities=t.cities, treasury=t.nh_coins, shield_seconds=await ttl_seconds(redis, empire_war_shield(t.user_id)),
        )
        for t in result.items
    ]
    return WarTargetsOut(items=items, page=result.page, has_more=result.has_more)


class DeclareIn(BaseModel):
    target_id: int


@router.post("/war/declare", response_model=MessageOut)
async def post_war_declare(
    body: DeclareIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> MessageOut:
    try:
        issued = await declare_war(session, redis, user_id, body.target_id)
    except WarNotEmperorError:
        raise bad(WAR_NOT_EMPEROR_ALERT)
    except TargetNotEmperorError:
        raise bad(TARGET_NOT_EMPEROR_ALERT)
    except TargetHasNoCitiesError:
        raise bad(TARGET_NO_CITIES_ALERT)
    except TargetShieldedError as exc:
        raise bad(TARGET_SHIELDED_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)))
    except NoAttackersError:
        raise bad(NO_ATTACKERS)
    except OutgoingWarExistsError:
        raise bad(OUTGOING_WAR_EXISTS_ALERT)
    except TargetAtWarError:
        raise bad(TARGET_AT_WAR_ALERT)
    except WarOnCooldownError as exc:
        raise bad(WAR_COOLDOWN_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)))
    target = await get_by_id(session, body.target_id)
    window = format_countdown(issued.window_seconds)
    await push(
        issued.defender_id, NOTIFY_WAR_CALL,
        PUSH_WAR_DECLARED.format(attacker=esc(issued.attacker_label), window=window),
        reply_markup=war_accept_menu(issued.war_id),
    )
    defender = _name(target.username if target else None, target.display_name if target else None)
    return MessageOut(message=clean_label(WAR_DECLARED.format(defender=defender, window=window)))


class AcceptIn(BaseModel):
    war_id: int


class WarResultOut(BaseModel):
    message: str
    won: bool | None


@router.post("/war/accept", response_model=WarResultOut)
async def post_war_accept(
    body: AcceptIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> WarResultOut:
    from bot.handlers.empire import send_war_reports

    try:
        outcome = await accept_war(session, redis, user_id, body.war_id)
    except WarNotFoundError:
        raise bad(WAR_NOT_FOUND_ALERT)
    await with_bot_session(lambda bot, s: send_war_reports(bot, s, outcome))
    if outcome.resolution not in (WAR_ACCEPTED, WAR_FORFEIT):
        return WarResultOut(message="Война аннулирована — у сторон уже нет городов или трона.", won=None)
    won = not outcome.attacker_won
    text = "Победа! Ты отбил нападение." if won else "Поражение: император забрал часть казны и города."
    return WarResultOut(message=f"{text} Итог боя — в чате с ботом.", won=won)


class SabotageIn(BaseModel):
    action: str
    target_id: int | None = None  # помеченный игрок (путь Сенсорики); None — свой император


class SabotageOut(BaseModel):
    success: bool
    message: str


@router.post("/sabotage", response_model=SabotageOut)
async def post_sabotage(
    body: SabotageIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> SabotageOut:
    from bot.handlers.empire.sabotage import _fields

    await require_user(session, user_id)
    try:
        result = await sabotage(session, redis, user_id, body.action, target_id=body.target_id)
    except UnknownSabotageError:
        raise bad("Неизвестное действие.")
    except NotMarkedTargetError:
        raise bad(NOT_MARKED_ALERT)
    except NoEmperorError:
        raise bad(NO_EMPEROR)
    except NothingToStealError:
        raise bad(NOTHING_TO_STEAL_ALERT)
    except SabotageOnCooldownError as exc:
        raise bad(SABOTAGE_COOLDOWN_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)))
    fields = _fields(result)
    if not result.silent:
        note = PUSH_SABOTAGE_SUCCESS[result.action].format(**fields) if result.success else PUSH_SABOTAGE_FAIL
        await push(result.emperor_id, NOTIFY_SABOTAGE, note)
    text = SABOTAGE_SUCCESS[result.action].format(**fields) if result.success else SABOTAGE_FAIL
    return SabotageOut(success=result.success, message=clean_label(text))

