"""API-роутер Mini App: карта города игрока (районы, события на карте, быстрые счётчики).

Только чтение — бой/вызовы живут в `district.py`/`boss.py`. Данные собирает тот же сервисный
код, что экран карты бота (`services.district.get_city_map`, `services.event.list_active`).
Для круга и выше (бой за город целиком, карта страны) в Mini App пока показывается только
собственный город — управление городами страны остаётся в боте.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad, clean_label, require_user, ttl_seconds
from api.routers.img import ASSETS_DIR
from bot.cache.keys import battle_cooldown, boss_cooldown
from bot.config.country import COUNTRY_BY_CODE
from bot.config.event import ART_ALIASES, BOSS_ART, SCHOOL_TEACHER_ART, TECHNIQUE_TEACHER_ART
from bot.constant.event import BOSS_FRAGMENT, BOSSES, EVENT_BOSS, EVENT_SCHOOL_TEACHER, EVENT_TEACHER
from bot.constant.school import SCHOOLS
from bot.constant.unique_technique import TECHNIQUES
from bot.constant.phase import PHASE_FIST, PHASE_GANG
from bot.services.business import get_wallet
from bot.services.city import get_city
from bot.services.district import get_city_map, get_territory
from bot.services.empire import get_emperor
from bot.services.event import list_active as list_events
from bot.texts.event import BOSS_ABILITIES, BOSS_NAMES, FRAGMENT_NAMES
from bot.texts.school import SCHOOL_NAMES, SCHOOL_TEACHERS
from bot.texts.unique_technique import TEACHER_NAMES, TECHNIQUE_NAMES

router = APIRouter(prefix="/api/map", tags=["map"])

PAGE_SIZE = 12


# Папки выделенного арта (пользователь 2026-10-10): боссы, учителя техник, учителя статистов.
ART_FOLDERS = {"boss": "boss", "teacher": "teacher_ut", "school": "teacher_statist"}


def event_art(kind: str, code: str, fallback: dict[str, str | None]) -> str | None:
    """Арт события: выделенный файл в `assets/<kind>/`, если лежит на диске (имя — код или
    алиас из `bot.config.event.ART_ALIASES`, без учёта регистра и расширения png/jpg/webp),
    иначе подставной из конфига (`bot.config.event.art`), иначе None («нужен арт»)."""
    folder = ASSETS_DIR / kind
    if folder.is_dir():
        names = {code.lower(), *(a.lower() for a in ART_ALIASES.get(code, ()))}
        for f in folder.iterdir():
            if f.is_file() and f.stem.lower() in names and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                return f"{kind}/{f.name}"
    return fallback.get(code)


# Арт шапки по коду страны (assets/map); у стран без файла шапка рисуется градиентом.
_COUNTRY_ART_FILES: dict[str, str] = {
    "RU": "map/Russia.png", "US": "map/America.png", "JP": "map/Japan.png",
    "KR": "map/South_Korea.png", "MX": "map/Mexico.png",
    # Ждут файлы (2026-10-21): положить в assets/map — подхватятся без правок кода.
    "KZ": "map/Kazakhstan.png", "CN": "map/China.png",
}
COUNTRY_ART: dict[str, str] = {code: rel for code, rel in _COUNTRY_ART_FILES.items() if (ASSETS_DIR / rel).is_file()}


class CityOut(BaseModel):
    id: int
    name: str
    art: str | None
    country_name: str | None
    district_count: int


class EmperorOut(BaseModel):
    name: str
    tax_percent: int


class DistrictOut(BaseModel):
    id: int
    number: int
    kind: str  # mine | bot | player
    owner: str | None
    bot_rank: str | None = None
    bot_quantity: int | None = None
    bot_power: int | None = None


class MapEventOut(BaseModel):
    id: int
    kind: str  # boss | teacher | school
    code: str
    title: str
    subtitle: str | None = None
    image: str | None = None
    ends_in_seconds: int
    won: bool = False
    # Учителя: new — задание не взято, active — взято (выполняется), done — техника/учитель уже есть.
    state: str | None = None
    quest_complete: bool = False


class EmpireOut(BaseModel):
    """Своя империя — у игрока в фазе кулака (2026-10-14: карта императора не должна звать «воевать за город»)."""

    cities: int
    players: int
    tax_percent: int
    collected: int
    holdings: int


class MapOut(BaseModel):
    city: CityOut
    emperor: EmperorOut | None
    phase: str
    empire: EmpireOut | None = None
    can_attack: bool  # False у круга/кулака — они воюют за город целиком в боте
    districts: list[DistrictOut]
    page: int
    pages: int
    total: int
    mine: int
    bots: int
    others: int
    sole_owner: str | None
    my_districts: int
    influence: int
    income_per_minute: float
    attack_cooldown_seconds: int
    boss_cooldown_seconds: int = 0
    events: list[MapEventOut]


def _event_out(e) -> MapEventOut:
    if e.kind == EVENT_BOSS:
        kind = BOSS_FRAGMENT[e.code]
        return MapEventOut(
            id=e.id, kind="boss", code=e.code, title=BOSS_NAMES.get(e.code, e.code),
            subtitle=f"Победа даст {FRAGMENT_NAMES[kind]}. {BOSS_ABILITIES.get(e.code, '')}".strip(),
            image=event_art("boss", e.code, BOSS_ART), ends_in_seconds=e.ends_in_seconds, won=e.won,
        )
    if e.kind == EVENT_SCHOOL_TEACHER:
        return MapEventOut(
            id=e.id, kind="school", code=e.code, title=clean_label(SCHOOL_TEACHERS.get(e.code, e.code)),
            subtitle=f"Школа: {clean_label(SCHOOL_NAMES.get(e.code, e.code))}",
            image=event_art(ART_FOLDERS["school"], e.code, SCHOOL_TEACHER_ART),
            ends_in_seconds=e.ends_in_seconds, won=e.won,
        )
    return MapEventOut(
        id=e.id, kind="teacher", code=e.code, title=clean_label(TEACHER_NAMES.get(e.code, e.code)),
        subtitle=f"Техника: {clean_label(TECHNIQUE_NAMES.get(e.code, e.code))}",
        image=event_art(ART_FOLDERS["teacher"], e.code, TECHNIQUE_TEACHER_ART),
        ends_in_seconds=e.ends_in_seconds, won=e.won,
    )


async def _empire(session: AsyncSession, user) -> EmpireOut:
    from sqlalchemy import func, select

    from bot.db.models.business import Business
    from bot.services.empire import get_overview

    stats = await get_overview(session, user.id)
    holdings = int(await session.scalar(select(func.count(Business.id)).where(Business.holder_id == user.id)) or 0)
    return EmpireOut(cities=stats.cities, players=stats.players, tax_percent=stats.tax_percent, collected=stats.collected, holdings=holdings)


@router.get("", response_model=MapOut)
async def get_map(
    page: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> MapOut:
    user = await require_user(session, user_id)
    city = await get_city(session, user.city_id)
    city_map = await get_city_map(session, user)
    territory = await get_territory(session, user.id)
    tax = await get_emperor(session, user.id)
    wallet = await get_wallet(session, user.id)
    events = await list_events(session, user.id)

    total = len(city_map.districts)
    pages = max(1, -(-total // PAGE_SIZE))
    page = min(page, pages - 1)
    chunk = city_map.districts[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    country = COUNTRY_BY_CODE.get(city.country_code)

    return MapOut(
        city=CityOut(
            id=city.id, name=city.name, art=COUNTRY_ART.get(city.country_code), country_name=clean_label(country.name) if country else None,
            district_count=city.district_count,
        ),
        emperor=EmperorOut(
            name=tax.emperor_name or (f"@{tax.emperor_username}" if tax.emperor_username else "Император"),
            tax_percent=tax.percent,
        ) if tax else None,
        phase=user.phase,
        empire=await _empire(session, user) if user.phase == PHASE_FIST else None,
        can_attack=user.phase == PHASE_GANG,
        districts=[
            DistrictOut(
                id=d.id, number=d.number,
                kind="mine" if d.is_mine else "bot" if d.owner_id is None else "player",
                owner=d.owner_label, bot_rank=d.bot_rank, bot_quantity=d.bot_quantity, bot_power=d.bot_power,
            )
            for d in chunk
        ],
        page=page, pages=pages, total=total,
        mine=city_map.mine, bots=city_map.bots, others=city_map.others, sole_owner=city_map.sole_owner_label,
        my_districts=territory.districts, influence=territory.influence,
        income_per_minute=float(wallet.per_minute) if wallet else 0.0,
        attack_cooldown_seconds=await ttl_seconds(redis, battle_cooldown(user.id)),
        boss_cooldown_seconds=await ttl_seconds(redis, boss_cooldown(user.id)),
        events=[await _with_teacher_state(session, user.id, _event_out(e)) for e in events],
    )


async def _with_teacher_state(session: AsyncSession, user_id: int, out: MapEventOut) -> MapEventOut:
    """Статус учителя для кнопки «Взять задание» (как кнопки под учителем в боте)."""
    if out.kind not in ("teacher", "school"):
        return out
    from bot.services import school as school_svc
    from bot.services import unique_technique as tech_svc

    try:
        if out.kind == "teacher":
            view = await tech_svc.get_teacher(session, user_id, out.id)
            have = view.owned
        else:
            view = await school_svc.get_teacher(session, user_id, out.id)
            have = view.unlocked
    except (tech_svc.TeacherGoneError, school_svc.TeacherGoneError):
        return out
    out.state = "done" if have else "active" if view.quest else "new"
    out.quest_complete = bool(view.quest and view.quest.complete)
    return out


class MeetOut(BaseModel):
    message: str
    tasks: list[str]


@router.post("/events/{event_id}/meet", response_model=MeetOut)
async def post_meet(event_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> MeetOut:
    """Взять задание у учителя на карте — техник (`connect`) или школы статистов (`meet`), как в боте."""
    from bot.db.repositories import event as event_repo
    from bot.services import school as school_svc
    from bot.services import unique_technique as tech_svc
    from bot.texts import school as t_school
    from bot.texts import unique_technique as t_tech
    from bot.texts.dev_quest import TASK_LABELS

    await require_user(session, user_id)
    event = await event_repo.get_active(session, event_id, user_id)
    if event is None:
        raise bad(t_school.TEACHER_GONE_ALERT)
    try:
        if event.kind == EVENT_SCHOOL_TEACHER:
            quest = await school_svc.meet(session, user_id, event_id)
            title = clean_label(SCHOOL_TEACHERS.get(quest.ref, quest.ref))
            hint = "Выполни — и учитель появится в магазине (Тренировки → Школы статистов)."
        else:
            quest = await tech_svc.connect(session, user_id, event_id)
            title = clean_label(TEACHER_NAMES.get(quest.ref, quest.ref))
            hint = "Выполни — и получишь технику (Развитие → Техники)."
    except (school_svc.TeacherGoneError, tech_svc.TeacherGoneError):
        raise bad(t_school.TEACHER_GONE_ALERT)
    except school_svc.AlreadyUnlockedError:
        raise bad(t_school.ALREADY_UNLOCKED_ALERT)
    except tech_svc.TechniqueOwnedError:
        raise bad(t_tech.TECHNIQUE_OWNED_ALERT)
    except (school_svc.QuestAlreadyActiveError, tech_svc.QuestAlreadyActiveError):
        raise bad(t_school.QUEST_ACTIVE_ALERT)
    tasks = [f"{clean_label(TASK_LABELS.get(t, t))}: {min(quest.progress.get(t, 0), n)}/{n}" for t, n in quest.tasks.items()]
    return MeetOut(message=f"{title} даёт задание:\n" + "\n".join(tasks) + f"\n{hint}", tasks=tasks)


class CatalogEntryOut(BaseModel):
    kind: str  # boss | teacher | school
    code: str
    name: str
    subtitle: str
    image: str | None  # None -> «нужен арт»
    active: bool
    ends_in_seconds: int | None = None


class EventsCatalogOut(BaseModel):
    bosses: list[CatalogEntryOut]
    teachers: list[CatalogEntryOut]
    schools: list[CatalogEntryOut]


@router.get("/events-catalog", response_model=EventsCatalogOut)
async def get_events_catalog(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> EventsCatalogOut:
    """Все, кто может появиться на карте, с пометкой «активен сейчас» (для этого игрока)."""
    user = await require_user(session, user_id)
    active = {(e.kind, e.code): e for e in await list_events(session, user.id) if not e.won}

    def entry(kind: str, ev_kind: str, code: str, name: str, subtitle: str, art: dict[str, str | None]) -> CatalogEntryOut:
        ev = active.get((ev_kind, code))
        return CatalogEntryOut(
            kind=kind, code=code, name=clean_label(name), subtitle=subtitle,
            image=event_art(ART_FOLDERS[kind], code, art),
            active=ev is not None, ends_in_seconds=ev.ends_in_seconds if ev else None,
        )

    return EventsCatalogOut(
        bosses=[entry("boss", EVENT_BOSS, c, BOSS_NAMES.get(c, c), "босс", BOSS_ART) for c in BOSSES],
        teachers=[
            entry("teacher", EVENT_TEACHER, c, TEACHER_NAMES.get(c, c), clean_label(TECHNIQUE_NAMES.get(c, c)), TECHNIQUE_TEACHER_ART)
            for c in TECHNIQUES
        ],
        schools=[
            entry("school", EVENT_SCHOOL_TEACHER, c, SCHOOL_TEACHERS.get(c, c), f"школа {clean_label(SCHOOL_NAMES.get(c, c))}", SCHOOL_TEACHER_ART)
            for c in SCHOOLS
        ],
    )
