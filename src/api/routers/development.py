"""API-роутер Mini App: экран «Развитие» (путь, техники, гений, родословная, пробуждение).

Вся логика — в `bot.services.{unique_path,unique_technique,genius,bloodline,awakening}`
(те же сервисы, что вызывают хендлеры бота). Роутер только собирает вид экрана и
переводит исключения сервисов в 400 с русским текстом (тексты — из `bot.texts.*`).
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers.training import TrainingStatusOut, training_status
from bot.config import awakening as awakening_cfg
from bot.config import bloodline as bloodline_cfg
from bot.config import genius as genius_cfg
from bot.config import unique_path as path_cfg
from bot.config import unique_technique as tech_cfg
from bot.config.development import MAX_LEVEL, awakening_multiplier
from bot.constant.bloodline import BLOODLINES
from bot.constant.donate import KIND_GENIUS, KIND_PATH, KIND_TECHNIQUE
from bot.constant.genius import GENIUSES
from bot.db.repositories import donate as donate_repo
from bot.constant.unique_path import PATH_TRAINING
from bot.services import awakening as awakening_svc
from bot.services.build import get_build
from bot.services import bloodline as bloodline_svc
from bot.services import genius as genius_svc
from bot.services import unique_path as path_svc
from bot.services import unique_technique as tech_svc
from bot.services.dev_quest import QuestView
from bot.services.gang import get_gang
from bot.texts import awakening as t_awk
from bot.texts import bloodline as t_blood
from bot.texts import genius as t_gen
from bot.texts import unique_path as t_path
from bot.texts import unique_technique as t_tech
from bot.texts.dev_quest import TASK_LABELS
from bot.texts.development import describe_level
from bot.texts.profile import POTENTIAL_LABELS
from bot.utils.formatting import format_countdown

router = APIRouter(prefix="/api/development", tags=["development"])

Tab = Literal["path", "techniques", "genius", "blood", "awakening"]


# --- модели ---


class TaskOut(BaseModel):
    label: str
    done: int
    need: int


class QuestOut(BaseModel):
    ref: str
    title: str
    tasks: list[TaskOut]
    complete: bool


class LevelOut(BaseModel):
    n: int
    text: str
    state: Literal["done", "bought", "next", "locked"]  # bought — куплен за донат, ещё не открыт


class ItemOut(BaseModel):
    code: str
    name: str
    theme: str = ""
    level: int
    floor: int = 0  # купленный навсегда уровень (фиолетовый сегмент выше текущего)
    next_cost: int | None = None
    levels: list[LevelOut]


class DevelopmentOut(BaseModel):
    tab: Tab
    training: TrainingStatusOut
    max_level: int
    data: dict[str, Any]


# --- помощники ---


def _tasks(quest: QuestView | None) -> list[TaskOut]:
    if quest is None:
        return []
    return [
        TaskOut(label=TASK_LABELS.get(t, t), done=min(quest.progress.get(t, 0), n), need=n)
        for t, n in quest.tasks.items()
    ]


def _quest(quest: QuestView | None, title: str = "") -> dict | None:
    if quest is None:
        return None
    return QuestOut(ref=quest.ref, title=title, tasks=_tasks(quest), complete=quest.complete).model_dump()


def _levels(specs, level: int, floor: int = 0, special: dict | None = None) -> list[LevelOut]:
    out = []
    for n, spec in enumerate(specs, 1):
        if n <= level:
            state = "done"
        elif n <= floor:
            state = "bought"
        elif n == level + 1:
            state = "next"
        else:
            state = "locked"
        out.append(LevelOut(n=n, text=describe_level(spec, special) or "—", state=state))
    return out


def _item(code: str, name: str, theme: str, level: int, floor: int, next_cost: int | None, specs, special=None) -> dict:
    return ItemOut(
        code=code, name=name, theme=theme, level=level, floor=floor, next_cost=next_cost,
        levels=_levels(specs, level, floor, special),
    ).model_dump()


@contextmanager
def _errors(*mapping: tuple[type[Exception], Any]):
    """Исключение сервиса → 400 с русским текстом. Значение — строка или функция(exc) → строка."""
    try:
        yield
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        for cls, text in mapping:
            if isinstance(exc, cls):
                raise HTTPException(400, text(exc) if callable(text) else text) from exc
        raise


async def _guard(session: AsyncSession, user_id: int) -> None:
    if await get_gang(session, user_id) is None:
        raise HTTPException(404, "Игрок не найден")


def _cooldown_text(template: str):
    return lambda exc: template.format(countdown=format_countdown(exc.retry_after_seconds))


# --- GET ---


@router.get("", response_model=DevelopmentOut)
async def get_development(
    tab: Tab = "path",
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> DevelopmentOut:
    await _guard(session, user_id)
    builder = {
        "path": _path_tab, "techniques": _techniques_tab, "genius": _genius_tab,
        "blood": _blood_tab, "awakening": _awakening_tab,
    }[tab]
    data = await builder(session, redis, user_id)
    return DevelopmentOut(tab=tab, training=await training_status(redis, user_id), max_level=MAX_LEVEL, data=data)


async def _path_tab(session: AsyncSession, redis: Redis, user_id: int) -> dict:
    await path_svc.check_conviction(session, user_id)
    view = await path_svc.get_view(session, redis, user_id)
    floors = {c: lvl for (_, c), lvl in (await donate_repo.unlocks(session, user_id, KIND_PATH)).items()}

    def item(code: str) -> dict:
        level = view.owned.get(code, 0)
        cost = path_cfg.path_level_cost(level + 1) if level < MAX_LEVEL else None
        return _item(
            code, t_path.PATH_NAMES[code], t_path.PATH_THEMES[code], level, floors.get(code, 0), cost,
            path_cfg.LEVELS[code], t_path.SPECIAL_EFFECTS,
        )

    return {
        "stage": view.stage,  # 0 — копит ранги, 1 — квест убеждения, 2 — убеждение (фрагменты), 3 — путь есть
        "rank_sum": view.rank_sum,
        "rank_needed": view.rank_needed,
        "conviction_quest": _quest(view.quest, "Подтверждение убеждений"),
        "fragments": view.fragments,
        "awaken_cost": view.awaken_cost,
        "points": view.points,
        "swap_cooldown": view.swap_cooldown,
        "active": view.active,
        "active2": view.active2,
        "second_body": view.second_body,
        "next_cost": view.next_cost,
        "next_cost2": view.next_cost2,
        "owned": [item(c) for c in view.owned],
        "bought": [{"code": c, "name": t_path.PATH_NAMES[c]} for c in view.bought],
        # Путь тренировок: текущий КПД и потолок уровня (доли, 0…0.5).
        "training_kpd": (await get_build(session, user_id)).training_kpd,
        "training_kpd_cap": view.owned.get(PATH_TRAINING, 0) * path_cfg.TRAINING_KPD_CAP_PER_LEVEL,
    }


async def _techniques_tab(session: AsyncSession, redis: Redis, user_id: int) -> dict:
    view = await tech_svc.get_view(session, redis, user_id)
    floors = {c: lvl for (_, c), lvl in (await donate_repo.unlocks(session, user_id, KIND_TECHNIQUE)).items()}
    owned = [
        _item(
            c, t_tech.TECHNIQUE_NAMES[c], t_tech.TECHNIQUE_THEMES[c], lv, floors.get(c, 0),
            view.next_costs.get(c), tech_cfg.LEVELS[c], t_tech.SPECIAL_EFFECTS,
        )
        for c, lv in view.owned.items()
    ]
    quests = [
        {**_quest(q, f"{t_tech.TECHNIQUE_NAMES[q.ref]} ({t_tech.TEACHER_NAMES[q.ref]})"), "code": q.ref}
        for q in view.quests
    ]
    return {
        "active": view.active, "fragments": view.fragments, "swap_cooldown": view.swap_cooldown,
        "owned": owned, "quests": quests,
    }


async def _genius_tab(session: AsyncSession, redis: Redis, user_id: int) -> dict:
    await genius_svc.ensure_genius(session, user_id)
    view = await genius_svc.get_view(session, redis, user_id)
    floors = {c: lvl for (_, c), lvl in (await donate_repo.unlocks(session, user_id, KIND_GENIUS)).items()}
    owned = [
        _item(
            c, t_gen.GENIUS_NAMES[c], t_gen.GENIUS_THEMES[c], lv, floors.get(c, 0),
            view.next_costs.get(c), genius_cfg.LEVELS[c],
        )
        for c, lv in view.owned.items()
    ]
    return {
        "active": view.active, "fragments": view.fragments, "coins": view.coins,
        "swap_cooldown": view.swap_cooldown, "owned": owned,
        "roll_fragments": genius_cfg.GENIUS_ROLL_FRAGMENTS, "roll_coins": genius_cfg.GENIUS_ROLL_COINS,
        "total": len(GENIUSES),
    }


async def _blood_tab(session: AsyncSession, redis: Redis, user_id: int) -> dict:
    state = await bloodline_svc.get_state(session, user_id)
    body = await donate_repo.body_state(session, user_id)
    second_body = bool(body and body[0])
    if state is None or state.code is None:
        return {
            "chosen": False,
            "options": [
                {
                    "code": c,
                    "name": t_blood.BLOODLINE_NAMES[c],
                    "description": t_blood.BLOODLINE_DESCRIPTIONS.get(c, t_blood.BLOODLINE_NO_DESCRIPTION),
                    "first": describe_level(bloodline_cfg.LEVELS[c][0], t_blood.SPECIAL_EFFECTS),
                }
                for c in BLOODLINES
            ],
        }
    first = _item(
        state.code, t_blood.BLOODLINE_NAMES[state.code], t_blood.BLOODLINE_DESCRIPTIONS.get(state.code, ""),
        state.level, 0, state.next_cost, bloodline_cfg.LEVELS[state.code], t_blood.SPECIAL_EFFECTS,
    )
    second = None
    options2: list[dict] = []
    if second_body:
        _sb, _p2, _first, code2, level2, _drops = body
        if code2:
            cost2 = bloodline_cfg.bloodline_level_cost(level2 + 1) if level2 < MAX_LEVEL else None
            second = _item(
                code2, t_blood.BLOODLINE_NAMES[code2], t_blood.BLOODLINE_DESCRIPTIONS.get(code2, ""),
                level2, 0, cost2, bloodline_cfg.LEVELS[code2], t_blood.SPECIAL_EFFECTS,
            )
        else:
            options2 = [{"code": c, "name": t_blood.BLOODLINE_NAMES[c]} for c in BLOODLINES if c != state.code]
    return {
        "chosen": True, "blood_drops": state.blood_drops, "first": first,
        "second_body": second_body, "second": second, "options2": options2,
    }


async def _awakening_tab(session: AsyncSession, redis: Redis, user_id: int) -> dict:
    view = await awakening_svc.get_view(session, user_id)
    levels = [
        {
            "n": n, "mult": awakening_multiplier(n), "text": describe_level(spec) or "—",
            "state": "done" if n <= view.level else ("next" if n == view.level + 1 else "locked"),
        }
        for n, spec in enumerate(awakening_cfg.LEVELS, 1)
    ]
    return {
        "level": view.level, "max": awakening_cfg.AWAKENING_MAX, "multiplier": view.multiplier,
        "next_multiplier": view.next_multiplier, "is_emperor": view.is_emperor, "maxed": view.maxed,
        "ready": view.ready, "next_floor": POTENTIAL_LABELS[view.next_floor], "next_blood": view.next_blood,
        "quest": _quest(view.quest, f"Квест кулака на этап {view.level + 1}"), "levels": levels,
        "confirm_seconds": awakening_cfg.AWAKEN_CONFIRM_SECONDS,
    }


# --- POST: путь ---


class CodeBody(BaseModel):
    code: str


class SlotBody(BaseModel):
    slot: int = 1


class AwakenPathBody(BaseModel):
    choice: str | None = None  # код купленного пути; None — случайный


class ActivateBody(BaseModel):
    code: str
    slot: int = 1


_PATH_ERRORS = (
    (path_svc.QuestNotCompleteError, t_path.QUEST_NOT_DONE_ALERT),
    (path_svc.WrongStageError, t_path.WRONG_STAGE_ALERT),
    (path_svc.PathNotOwnedError, t_path.NOT_OWNED_ALERT),
    (path_svc.PathMaxLevelError, t_path.MAX_LEVEL_ALERT),
    (path_svc.NotEnoughFragmentsError, lambda e: t_path.NOT_ENOUGH_FRAGMENTS_ALERT.format(cost=e.cost, have=e.have)),
    (path_svc.NotEnoughPointsError, lambda e: t_path.NOT_ENOUGH_ALERT.format(cost=e.cost, have=e.have)),
    (path_svc.NoSecondBodyError, t_path.NO_SECOND_BODY_ALERT),
    (path_svc.SwapOnCooldownError, _cooldown_text(t_path.SWAP_COOLDOWN_ALERT)),
)


@router.post("/path/conviction")
async def post_path_conviction(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await _guard(session, user_id)
    with _errors(*_PATH_ERRORS):
        await path_svc.claim_conviction(session, user_id)
    return {"message": "Убеждение получено — копи фрагменты пути."}


@router.post("/path/awaken")
async def post_path_awaken(
    body: AwakenPathBody, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await _guard(session, user_id)
    with _errors(*_PATH_ERRORS):
        code = await path_svc.awaken_path(session, user_id, choice=body.choice or None)
    return {"message": f"Путь пробуждён: {t_path.PATH_NAMES[code]}", "code": code}


@router.post("/path/level-up")
async def post_path_level_up(
    body: SlotBody, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await _guard(session, user_id)
    with _errors(*_PATH_ERRORS):
        level = await path_svc.level_up(session, user_id, slot=2 if body.slot == 2 else 1)
    return {"message": f"Путь: уровень {level}", "level": level}


@router.post("/path/activate")
async def post_path_activate(
    body: ActivateBody,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await _guard(session, user_id)
    with _errors(*_PATH_ERRORS):
        if body.slot == 2:
            await path_svc.activate2(session, redis, user_id, body.code)
        else:
            await path_svc.activate(session, redis, user_id, body.code)
    return {"message": t_path.ACTIVATED_ALERT.format(name=t_path.PATH_NAMES.get(body.code, body.code))}


# --- POST: техники ---

_TECH_ERRORS = (
    (tech_svc.UnknownTechniqueError, t_tech.NOT_OWNED_ALERT),
    (tech_svc.TechniqueNotOwnedError, t_tech.NOT_OWNED_ALERT),
    (tech_svc.TechniqueMaxLevelError, t_tech.MAX_LEVEL_ALERT),
    (tech_svc.QuestNotCompleteError, t_tech.QUEST_NOT_DONE_ALERT),
    (tech_svc.NotEnoughFragmentsError, lambda e: t_tech.NOT_ENOUGH_ALERT.format(cost=e.cost, have=e.have)),
    (tech_svc.SwapOnCooldownError, _cooldown_text(t_tech.SWAP_COOLDOWN_ALERT)),
    (tech_svc.TrainingRequiredError, "Сначала тренировка у учителя: Развитие → Тренировки → Тренировка техники."),
)


@router.post("/technique/activate")
async def post_technique_activate(
    body: CodeBody,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await _guard(session, user_id)
    with _errors(*_TECH_ERRORS):
        await tech_svc.activate(session, redis, user_id, body.code)
    return {"message": t_tech.ACTIVATED_ALERT.format(name=t_tech.TECHNIQUE_NAMES.get(body.code, body.code))}


@router.post("/technique/level-up")
async def post_technique_level_up(
    body: CodeBody, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await _guard(session, user_id)
    with _errors(*_TECH_ERRORS):
        level = await tech_svc.level_up(session, user_id, body.code)
    return {"message": t_tech.LEVEL_UP_ALERT.format(name=t_tech.TECHNIQUE_NAMES[body.code], level=level), "level": level}


@router.post("/technique/claim")
async def post_technique_claim(
    body: CodeBody, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await _guard(session, user_id)
    with _errors(*_TECH_ERRORS):
        await tech_svc.claim_teacher_quest(session, user_id, body.code)
    return {"message": f"Получена техника: {t_tech.TECHNIQUE_NAMES[body.code]}"}


# --- POST: гений ---


def _genius_fragments_text(exc) -> str:
    if exc.cost == genius_cfg.GENIUS_ROLL_FRAGMENTS:
        return t_gen.NOT_ENOUGH_ROLL_ALERT
    return t_gen.NOT_ENOUGH_ALERT.format(cost=exc.cost, have=exc.have)


_GENIUS_ERRORS = (
    (genius_svc.UnknownGeniusError, t_gen.NOT_OWNED_ALERT),
    (genius_svc.GeniusNotOwnedError, t_gen.NOT_OWNED_ALERT),
    (genius_svc.GeniusMaxLevelError, t_gen.MAX_LEVEL_ALERT),
    (genius_svc.GeniusBusyError, t_gen.BUSY_ALERT),
    (genius_svc.NotEnoughFragmentsError, _genius_fragments_text),
    (genius_svc.SwapOnCooldownError, _cooldown_text(t_gen.SWAP_COOLDOWN_ALERT)),
)


@router.post("/genius/activate")
async def post_genius_activate(
    body: CodeBody,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await _guard(session, user_id)
    with _errors(*_GENIUS_ERRORS):
        await genius_svc.activate(session, redis, user_id, body.code)
    return {"message": t_gen.ACTIVATED_ALERT.format(name=t_gen.GENIUS_NAMES.get(body.code, body.code))}


@router.post("/genius/level-up")
async def post_genius_level_up(
    body: CodeBody, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await _guard(session, user_id)
    with _errors(*_GENIUS_ERRORS):
        level = await genius_svc.level_up(session, user_id, body.code)
    return {"message": t_gen.LEVEL_UP_ALERT.format(name=t_gen.GENIUS_NAMES[body.code], level=level), "level": level}


@router.post("/genius/roll")
async def post_genius_roll(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await _guard(session, user_id)
    with _errors(*_GENIUS_ERRORS):
        result = await genius_svc.roll(session, redis, user_id)
    name = t_gen.GENIUS_NAMES[result.code]
    message = f"Выпало: {name} — уже есть, крутка потеряна." if result.duplicate else f"Новая гениальность: {name}!"
    return {"message": message, "code": result.code, "duplicate": result.duplicate}


# --- POST: родословная ---

_BLOOD_ERRORS = (
    (bloodline_svc.UnknownBloodlineError, t_blood.ALREADY_CHOSEN_ALERT),
    (bloodline_svc.BloodlineAlreadyChosenError, t_blood.ALREADY_CHOSEN_ALERT),
    (bloodline_svc.NoBloodlineError, "Сначала выбери родословную."),
    (bloodline_svc.BloodlineMaxLevelError, t_blood.MAX_LEVEL_ALERT),
    (bloodline_svc.NotEnoughBloodError, lambda e: t_blood.NOT_ENOUGH_BLOOD_ALERT.format(cost=e.cost, have=e.have)),
    (bloodline_svc.NoSecondBodyError, t_blood.NO_SECOND_BODY_ALERT),
)


@router.post("/bloodline/choose")
async def post_bloodline_choose(
    body: CodeBody, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await _guard(session, user_id)
    with _errors(*_BLOOD_ERRORS):
        await bloodline_svc.choose(session, user_id, body.code)
    return {"message": f"Родословная выбрана: {t_blood.BLOODLINE_NAMES[body.code]}"}


@router.post("/bloodline/level-up")
async def post_bloodline_level_up(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await _guard(session, user_id)
    with _errors(*_BLOOD_ERRORS):
        level = await bloodline_svc.level_up(session, user_id)
    return {"message": t_blood.LEVEL_UP_ALERT.format(level=level), "level": level}


@router.post("/bloodline/choose2")
async def post_bloodline_choose2(
    body: CodeBody, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await _guard(session, user_id)
    with _errors(*_BLOOD_ERRORS):
        await bloodline_svc.choose2(session, user_id, body.code)
    return {"message": t_blood.PICKED_ALERT.format(name=t_blood.BLOODLINE_NAMES[body.code])}


@router.post("/bloodline/level-up2")
async def post_bloodline_level_up2(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await _guard(session, user_id)
    with _errors(*_BLOOD_ERRORS):
        level = await bloodline_svc.level_up2(session, user_id)
    return {"message": f"Вторая родословная: уровень {level}", "level": level}


# --- POST: пробуждение ---

_AWK_ERRORS = (
    (awakening_svc.AwakeningMaxedError, t_awk.MAXED_ALERT),
    (awakening_svc.NotEmperorError, t_awk.NOT_EMPEROR_ALERT),
    (awakening_svc.QuestNotCompleteError, t_awk.QUEST_NOT_DONE_ALERT),
    (awakening_svc.ConfirmExpiredError, t_awk.CONFIRM_EXPIRED_ALERT),
)


@router.post("/awakening/request")
async def post_awakening_request(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    """Первое нажатие: ставит флаг подтверждения (секунды на «Да»). Необратимо — второе нажатие
    (`/awakening/confirm`) должно прийти в этот срок."""
    await _guard(session, user_id)
    with _errors(*_AWK_ERRORS):
        seconds = await awakening_svc.request(session, redis, user_id)
    return {"message": f"Подтверди пробуждение в течение {seconds} с.", "seconds": seconds}


@router.post("/awakening/confirm")
async def post_awakening_confirm(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await _guard(session, user_id)
    with _errors(*_AWK_ERRORS):
        result = await awakening_svc.awaken(session, redis, user_id)
    return {
        "message": (
            f"Пробуждение {result.level}! Множитель ×{result.multiplier:g}, "
            f"потенциал: {POTENTIAL_LABELS[result.potential]}, капли крови +{result.blood}"
        ),
        "level": result.level,
    }
