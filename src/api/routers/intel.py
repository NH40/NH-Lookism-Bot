"""Разведка в Mini App — отчёт по @нику, метки и лента меток. Логика — `services/intel` (та же,
что у экрана разведки бота); саботаж помеченного — `POST /api/empire/sabotage` с `target_id`."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from redis.asyncio import Redis

from bot.services.intel import UnmarkableError
from bot.texts.intel import UNMARKABLE_ALERT
from api.deps import get_redis
from api.push import push
from bot.constant.settings import NOTIFY_SABOTAGE
from bot.db.repositories.activity import list_marks
from bot.db.repositories.user import get_by_id
from bot.services.build import get_build
from bot.services.intel import (
    NoScoutError,
    ScoutTargetError,
    get_scout_report,
    list_scout_reports,
    scout,
    scout_ago,
    scout_levels,
    scout_report_lines,
)
from bot.texts.intel import NO_REPORTS, NO_SCOUT_ALERT, PUSH_SCOUTED, PUSH_SCOUTED_BY
from bot.utils.formatting import esc
from api.auth import get_current_user_id
from api.db import get_session
from api.routers._common import bad, clean_label, require_user
from bot.constant.empire import SABOTAGE_ACTIONS
from bot.config.empire import SABOTAGE_CHANCE_PERCENT
from bot.services.intel import MarksFullError, NoIntelError, TargetNotFoundError, get_access, get_marks_feed, get_report, toggle_mark
from bot.texts.bloodline import BLOODLINE_NAMES
from bot.texts.empire import SABOTAGE_LABELS
from bot.texts.genius import GENIUS_NAMES
from bot.texts.intel import MARKED_ALERT, MARKS_FULL_ALERT, NO_ACCESS_ALERT, NOT_FOUND, UNMARKED_ALERT
from bot.texts.unique_path import PATH_NAMES
from bot.texts.unique_technique import TECHNIQUE_NAMES

router = APIRouter(prefix="/api/intel", tags=["intel"])


def _name(username: str | None, display_name: str | None) -> str:
    return display_name or (f"@{username}" if username else "Игрок")


class LogOut(BaseModel):
    at: datetime
    text: str


class CampOut(BaseModel):
    power: int
    quantity: int
    top: list[tuple[str, int]]


class BuildItemOut(BaseModel):
    system: str
    name: str
    level: int


class ReportOut(BaseModel):
    target_id: int
    name: str
    username: str | None
    hidden: bool  # скрытность цели — отчёт закрыт
    scout: int
    logs: int
    attack: CampOut | None
    defense: CampOut | None
    build: list[BuildItemOut] | None
    entries: list[LogOut]
    marked: bool
    can_mark: bool
    can_sabotage: bool
    sabotage_actions: list[tuple[str, str, int]]  # (код, подпись, шанс) — для саботажа помеченного


class MarkFeedOut(BaseModel):
    target_id: int
    name: str
    hidden: bool
    entries: list[LogOut]


class IntelOut(BaseModel):
    scout: int
    logs: int
    fields: int  # сколько полей открывает разведка (навыки позиции Разведки и системы развития)
    marks_limit: int
    marks: list[MarkFeedOut]


@router.get("", response_model=IntelOut)
async def get_intel(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> IntelOut:
    await require_user(session, user_id)
    access = await get_access(session, user_id)
    limit, feeds = await get_marks_feed(session, user_id)
    return IntelOut(
        scout=access.scout, logs=access.logs, fields=len(await scout_levels(session, user_id)), marks_limit=limit,
        marks=[
            MarkFeedOut(target_id=f.target_id, name=_name(f.username, f.display_name), hidden=f.hidden,
                        entries=[LogOut(at=t, text=x) for t, x in f.entries])
            for f in feeds
        ],
    )


def _camp(camp) -> CampOut | None:
    return CampOut(power=camp.power, quantity=camp.quantity, top=list(camp.top)) if camp is not None else None


@router.get("/report", response_model=ReportOut)
async def get_intel_report(
    username: str = Query(..., min_length=1, max_length=64),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ReportOut:
    await require_user(session, user_id)
    try:
        r = await get_report(session, user_id, username.strip())
    except NoIntelError:
        raise bad(clean_label(NO_ACCESS_ALERT))
    except TargetNotFoundError:
        raise bad(clean_label(NOT_FOUND))
    build = None
    if r.build is not None:
        b = r.build
        parts = [
            ("Родословная", BLOODLINE_NAMES.get(b.bloodline), b.bloodline_level), ("Путь", PATH_NAMES.get(b.path), b.path_level),
            ("Техника", TECHNIQUE_NAMES.get(b.technique), b.technique_level), ("Гений", GENIUS_NAMES.get(b.genius), b.genius_level),
        ]
        build = [BuildItemOut(system=s, name=clean_label(n), level=lv) for s, n, lv in parts if n]
    return ReportOut(
        target_id=r.target_id, name=_name(r.username, r.display_name), username=r.username, hidden=r.stealth_hidden,
        scout=r.scout, logs=r.logs, attack=_camp(r.attack), defense=_camp(r.defense), build=build,
        entries=[LogOut(at=t, text=x) for t, x in r.entries], marked=r.marked, can_mark=r.can_mark, can_sabotage=r.can_sabotage,
        sabotage_actions=[(a, clean_label(SABOTAGE_LABELS[a]), SABOTAGE_CHANCE_PERCENT[a]) for a in SABOTAGE_ACTIONS] if r.can_sabotage else [],
    )


class ScoutFieldOut(BaseModel):
    field: str
    label: str
    value: str
    seen: str  # exact | range | hidden


class ScoutReportOut(BaseModel):
    target_id: int
    name: str
    ago: str
    fields: list[ScoutFieldOut]
    trap_lost: int = 0
    marked: bool
    can_mark: bool
    can_sabotage: bool
    sabotage_actions: list[tuple[str, str, int]]


class ScoutIn(BaseModel):
    username: str | None = None
    target_id: int | None = None


class ScoutRowOut(BaseModel):
    target_id: int
    name: str
    ago: str


async def _scout_out(session: AsyncSession, viewer_id: int, target_id: int, payload: dict, created_at, trap: int = 0) -> ScoutReportOut:
    access = await get_access(session, viewer_id)
    marks = await list_marks(session, viewer_id)
    flags = (await get_build(session, viewer_id)).flags
    marked = target_id in marks
    can_sabotage = marked and "sabotage_marked" in flags
    return ScoutReportOut(
        target_id=target_id, name=payload.get("_target", "—"), ago=scout_ago(created_at),
        fields=[ScoutFieldOut(field=f, label=label, value=value, seen=payload[f]["seen"]) for f, label, value in scout_report_lines(payload)],
        trap_lost=trap, marked=marked, can_mark=access.marks > 0, can_sabotage=can_sabotage,
        sabotage_actions=[(a, clean_label(SABOTAGE_LABELS[a]), SABOTAGE_CHANCE_PERCENT[a]) for a in SABOTAGE_ACTIONS] if can_sabotage else [],
    )


@router.post("/scout", response_model=ScoutReportOut)
async def post_scout(
    body: ScoutIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> ScoutReportOut:
    """Разведать игрока — отдельный этап, без КД; отчёт сохраняется."""
    await require_user(session, user_id)
    try:
        r = await scout(session, redis, user_id, target_id=body.target_id, username=body.username)
    except NoScoutError:
        raise bad(clean_label(NO_SCOUT_ALERT))
    except ScoutTargetError:
        raise bad(clean_label(NOT_FOUND))
    if r.notify_target == "double_agent":
        viewer = await get_by_id(session, user_id)
        name = (viewer.display_name or (f"@{viewer.username}" if viewer.username else "—")) if viewer else "—"
        await push(r.target_id, NOTIFY_SABOTAGE, PUSH_SCOUTED_BY.format(name=esc(name)))
    elif r.notify_target == "alarm":
        await push(r.target_id, NOTIFY_SABOTAGE, PUSH_SCOUTED)
    return await _scout_out(session, user_id, r.target_id, r.payload, r.created_at, r.trap_lost)


@router.get("/reports", response_model=list[ScoutRowOut])
async def get_scout_reports(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> list[ScoutRowOut]:
    return [ScoutRowOut(target_id=r.target_id, name=r.payload.get("_target", "—"), ago=scout_ago(r.created_at))
            for r in await list_scout_reports(session, user_id)]


@router.get("/scout/{target_id}", response_model=ScoutReportOut)
async def get_saved_report(target_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> ScoutReportOut:
    row = await get_scout_report(session, user_id, target_id)
    if row is None:
        raise bad(clean_label(NO_REPORTS))
    return await _scout_out(session, user_id, row.target_id, row.payload, row.created_at)


class MarkIn(BaseModel):
    target_id: int


class MarkOut(BaseModel):
    message: str
    marked: bool


@router.post("/mark", response_model=MarkOut)
async def post_mark(body: MarkIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> MarkOut:
    await require_user(session, user_id)
    try:
        marked = await toggle_mark(session, user_id, body.target_id)
    except UnmarkableError:
        raise bad(UNMARKABLE_ALERT)
    except MarksFullError as exc:
        raise bad(MARKS_FULL_ALERT.format(limit=exc.limit))
    return MarkOut(message=MARKED_ALERT if marked else UNMARKED_ALERT, marked=marked)
