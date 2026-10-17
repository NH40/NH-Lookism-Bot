"""API-роутер Mini App: тренировки (личная и статистов). Бизнес-логика — только
`bot.services.training` (тот же сервис, что вызывает `bot.handlers.training`)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from bot.cache.keys import last_extras_training, train_extras_cooldown
from bot.config.characteristic import POTENTIAL_TRAINING
from bot.config.school import SCHOOL_LESSON_PRICE
from bot.config.game import (
    EXTRA_TRAINING_COOLDOWN_SECONDS,
    EXTRA_TRAINING_COVERAGE_PERCENT,
    EXTRA_TRAINING_MAX_STARS,
    EXTRA_TRAINING_STAGE1_POWER_MULTIPLIER,
    EXTRA_TRAINING_STAGE1_SUCCESS_PERCENT,
    EXTRA_TRAINING_STAGE2_POWER_BONUS_PERCENT,
    EXTRA_TRAINING_STAGE2_SUCCESS_PERCENT,
    EXTRA_TRAINING_STAGE3_SUCCESS_PERCENT,
    PERSONAL_TRAINING_COOLDOWN_SECONDS,
)
from bot.db.repositories.user import get_by_id
from bot.services.business import gym_training_bonus_percent
from bot.services.characteristic import get_combat_profile, get_stats_view
from bot.services.extra import get_army_stats
from bot.services.gang import get_gang
from bot.services.training import TrainingOnCooldownError, personal_cooldown_left, train_extras, train_personal
from bot.texts.profile import POTENTIAL_LABELS
from bot.utils.formatting import format_countdown, format_number

router = APIRouter(prefix="/api/training", tags=["training"])


class PersonalOut(BaseModel):
    left: int
    total: int
    min_points: int
    max_points: int
    nothing_percent: int
    potential: str
    dev_points: int


class StageOut(BaseModel):
    n: int
    label: str
    percent: int


class ExtrasOut(BaseModel):
    left: int
    total: int
    coverage_percent: int
    stages: list[StageOut]
    gym_bonus: int
    has_extras: bool


class LastExtrasOut(BaseModel):
    attempted: int
    stage1: int
    stage2: int
    stage3: int


class TechTaskOut(BaseModel):
    label: str
    done: int
    need: int


class TechTrainingOut(BaseModel):
    code: str
    name: str
    teacher: str
    level: int
    next_level: int | None
    stage: str  # pay / quest / level / max
    price: int
    fragments_cost: int
    tasks: list[TechTaskOut]


class TechniquesOut(BaseModel):
    items: list[TechTrainingOut]
    fragments: int
    coins: int


class SchoolOut(BaseModel):
    code: str
    teacher: str
    school: str
    effect: str
    state: str  # owned / unlocked / locked
    cooldown: int
    # locked: взятое задание учителя (его берут у учителя на карте); unlocked: цена покупки.
    quest: dict | None = None
    price: int = 0


class TrainingOut(BaseModel):
    personal: PersonalOut
    extras: ExtrasOut
    last_extras: LastExtrasOut | None = None
    techniques: TechniquesOut | None = None
    schools: list[SchoolOut] = []
    school_lesson_price: int = 0


class TrainingStatusOut(BaseModel):
    personal_left: int
    extras_left: int


async def training_status(redis: Redis, user_id: int) -> TrainingStatusOut:
    """Живой статус для строки «Тренировки» на экране «Развитие»."""
    return TrainingStatusOut(
        personal_left=await personal_cooldown_left(redis, user_id),
        extras_left=max(0, await redis.ttl(train_extras_cooldown(user_id))),
    )


async def _user(session: AsyncSession, user_id: int):
    user = await get_by_id(session, user_id)
    if user is None or await get_gang(session, user_id) is None:
        raise HTTPException(404, "Игрок не найден")
    return user


LAST_EXTRAS_TTL_SECONDS = 24 * 60 * 60


async def _techniques(session: AsyncSession, user_id: int) -> TechniquesOut:
    """Тренировка техники (2026-10-12) — та же стадия, что в боте (`services.unique_technique.training`)."""
    from bot.services.unique_technique import list_trainings
    from bot.texts.dev_quest import TASK_LABELS
    from bot.texts.unique_technique import TEACHER_NAMES, TECHNIQUE_NAMES

    rows, fragments, coins = await list_trainings(session, user_id)
    items = []
    for r in rows:
        tasks, progress = (r.quest.tasks, r.quest.progress) if r.quest else (r.tasks, {})
        items.append(TechTrainingOut(
            code=r.code, name=TECHNIQUE_NAMES[r.code], teacher=TEACHER_NAMES[r.code], level=r.level, next_level=r.next_level,
            stage=r.stage, price=r.price, fragments_cost=r.fragments_cost,
            tasks=[TechTaskOut(label=TASK_LABELS.get(t, t), done=min(progress.get(t, 0), n), need=n) for t, n in tasks.items()],
        ))
    return TechniquesOut(items=items, fragments=fragments, coins=coins)


class TechCodeIn(BaseModel):
    code: str


@router.post("/technique/pay")
async def post_tech_pay(
    body: TechCodeIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    from bot.services.unique_technique import TechniqueMaxLevelError, TechniqueNotOwnedError, TrainingActiveError, TrainingCoinsError, start_training

    await _user(session, user_id)
    try:
        await start_training(session, user_id, body.code)
    except (TechniqueNotOwnedError, TechniqueMaxLevelError):
        raise HTTPException(400, "Эту технику сейчас тренировать нельзя.")
    except TrainingActiveError:
        raise HTTPException(400, "Тренировка на этот уровень уже оплачена — выполняй квест.")
    except TrainingCoinsError as exc:
        raise HTTPException(400, f"Не хватает NHCoin: нужно {format_number(exc.cost)}, у тебя {format_number(exc.balance)}.")
    return {"message": "Тренировка оплачена — учитель дал квест."}


@router.post("/technique/level")
async def post_tech_level(
    body: TechCodeIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    from bot.services.unique_technique import (
        NotEnoughFragmentsError,
        TechniqueMaxLevelError,
        TechniqueNotOwnedError,
        TrainingRequiredError,
        level_up,
    )
    from bot.texts.unique_technique import TECHNIQUE_NAMES

    await _user(session, user_id)
    try:
        level = await level_up(session, user_id, body.code)
    except (TechniqueNotOwnedError, TechniqueMaxLevelError):
        raise HTTPException(400, "Эту технику сейчас поднять нельзя.")
    except TrainingRequiredError:
        raise HTTPException(400, "Сначала выполни квест учителя.")
    except NotEnoughFragmentsError as exc:
        raise HTTPException(400, f"Не хватает фрагментов техники: нужно {exc.cost}, у тебя {exc.have}.")
    return {"message": f"{TECHNIQUE_NAMES[body.code]}: уровень {level}", "level": level}


async def _last_extras(redis: Redis, user_id: int) -> LastExtrasOut | None:
    raw = await redis.get(last_extras_training(user_id))
    try:
        return LastExtrasOut(**json.loads(raw)) if raw else None
    except (ValueError, TypeError):
        return None


@router.get("", response_model=TrainingOut)
async def get_training(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> TrainingOut:
    await _user(session, user_id)
    status = await training_status(redis, user_id)
    view = await get_stats_view(session, user_id)
    profile = await get_combat_profile(session, user_id)
    table = POTENTIAL_TRAINING[view.potential]
    gym = await gym_training_bonus_percent(session, user_id) + profile.eco.extras_training
    chance = lambda base: int(min(100, base + gym))  # noqa: E731
    stages = [
        StageOut(
            n=1,
            label=f"Мощь ×{EXTRA_TRAINING_STAGE1_POWER_MULTIPLIER:g}".replace(".", ","),
            percent=chance(EXTRA_TRAINING_STAGE1_SUCCESS_PERCENT),
        ),
        StageOut(
            n=2,
            label=f"Звезда пробуждения, +{EXTRA_TRAINING_STAGE2_POWER_BONUS_PERCENT}% мощи (до {EXTRA_TRAINING_MAX_STARS})",
            percent=chance(EXTRA_TRAINING_STAGE2_SUCCESS_PERCENT),
        ),
        StageOut(n=3, label="Повышение ранга на ступень", percent=chance(EXTRA_TRAINING_STAGE3_SUCCESS_PERCENT)),
    ]
    army = await get_army_stats(session, user_id)
    return TrainingOut(
        personal=PersonalOut(
            left=status.personal_left,
            total=profile.cooldown(PERSONAL_TRAINING_COOLDOWN_SECONDS, profile.eco.personal_cooldown),
            min_points=table.min_points,
            max_points=table.max_points,
            nothing_percent=table.nothing_percent,
            potential=POTENTIAL_LABELS[view.potential],
            dev_points=view.dev_points,
        ),
        extras=ExtrasOut(
            left=status.extras_left,
            total=profile.cooldown(EXTRA_TRAINING_COOLDOWN_SECONDS, profile.eco.extras_training_cooldown),
            coverage_percent=EXTRA_TRAINING_COVERAGE_PERCENT,
            stages=stages,
            gym_bonus=int(gym),
            has_extras=army.total_quantity > 0,
        ),
        last_extras=await _last_extras(redis, user_id),
        techniques=await _techniques(session, user_id),
        schools=await _schools(session, redis, user_id),
        school_lesson_price=SCHOOL_LESSON_PRICE,
    )


class SchoolIn(BaseModel):
    school: str


async def _schools(session: AsyncSession, redis: Redis, user_id: int) -> list[SchoolOut]:
    """Школы статистов (2026-10-13: занятия — в тренировках, покупка учителя — в магазине)."""
    from api.routers.development import _quest
    from bot.config.school import SCHOOL_TEACHER_PRICE
    from bot.constant.school import SCHOOLS
    from bot.services.school import quests, shop_teachers
    from bot.texts.school import SCHOOL_EFFECTS, SCHOOL_NAMES, SCHOOL_TEACHERS

    teachers = {t.school: t for t in await shop_teachers(session, redis, user_id)}
    active = {q.ref: q for q in await quests(session, user_id)}
    out = []
    for s in SCHOOLS:
        t = teachers.get(s)
        state = "owned" if t and t.owned else "unlocked" if t else "locked"
        out.append(SchoolOut(
            code=s, teacher=SCHOOL_TEACHERS[s], school=SCHOOL_NAMES[s], effect=SCHOOL_EFFECTS[s], state=state,
            cooldown=t.cooldown if t and t.owned else 0,
            quest=_quest(active.get(s), SCHOOL_TEACHERS[s]) if state == "locked" else None,
            price=SCHOOL_TEACHER_PRICE if state == "unlocked" else 0,
        ))
    return out


@router.post("/school/claim")
async def post_school_claim(
    body: SchoolIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    """Выполненное задание учителя → учитель в магазине (как «Позвать» в боте)."""
    from bot.services.school import QuestNotCompleteError, UnknownSchoolError, claim_quest
    from bot.texts.school import QUEST_NOT_DONE_ALERT, SCHOOL_TEACHERS

    await _user(session, user_id)
    try:
        await claim_quest(session, user_id, body.school)
    except (UnknownSchoolError, QuestNotCompleteError):
        raise HTTPException(400, QUEST_NOT_DONE_ALERT)
    return {"message": f"Учитель {SCHOOL_TEACHERS[body.school]} теперь доступен — купи его, чтобы открыть занятия."}


@router.post("/school/buy")
async def post_school_buy(
    body: SchoolIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    from bot.services.school import NotEnoughCoinsError as BuyCoinsError, SchoolBusyError, TeacherAlreadyOwnedError, TeacherNotUnlockedError, buy_teacher
    from bot.texts.school import BOUGHT_ALERT, SCHOOL_TEACHERS

    await _user(session, user_id)
    try:
        await buy_teacher(session, redis, user_id, body.school)
    except SchoolBusyError:
        raise HTTPException(400, "Обрабатываю…")
    except TeacherNotUnlockedError:
        raise HTTPException(400, "Сначала выполни задание этого учителя — его дают на карте.")
    except TeacherAlreadyOwnedError:
        raise HTTPException(400, "Этот учитель уже твой.")
    except BuyCoinsError as exc:
        raise HTTPException(400, f"Не хватает NHCoin: нужно {format_number(exc.cost)}.")
    return {"message": BOUGHT_ALERT.format(teacher=SCHOOL_TEACHERS[body.school])}


@router.post("/school/lesson")
async def post_school_lesson(
    body: SchoolIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    from bot.services.school import LessonOnCooldownError, NoStudentsError, NotEnoughCoinsError as LessonCoinsError, TeacherNotOwnedError, lesson
    from bot.texts.school import NO_STUDENTS_ALERT, NOT_OWNED_ALERT, SCHOOL_NAMES, SCHOOL_TEACHERS

    await _user(session, user_id)
    try:
        r = await lesson(session, redis, user_id, body.school)
    except TeacherNotOwnedError:
        raise HTTPException(400, NOT_OWNED_ALERT)
    except NoStudentsError:
        raise HTTPException(400, NO_STUDENTS_ALERT)
    except LessonOnCooldownError as exc:
        raise HTTPException(400, f"Занятие ещё на кулдауне — через {format_countdown(exc.retry_after_seconds)}.")
    except LessonCoinsError as exc:
        raise HTTPException(400, f"Не хватает NHCoin: нужно {format_number(exc.cost)}.")
    return {"message": f"{SCHOOL_TEACHERS[body.school]}: в школу «{SCHOOL_NAMES[body.school]}» вступили {format_number(r.joined)}, "
                       f"подняли уровень {format_number(r.leveled)}."}


@router.post("/personal")
async def post_personal(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await _user(session, user_id)
    try:
        result = await train_personal(session, redis, user_id)
    except TrainingOnCooldownError as exc:
        raise HTTPException(400, f"Личная тренировка ещё на кулдауне — через {format_countdown(exc.retry_after_seconds)}.")
    message = f"Получено очков развития: +{result.points}" if result.points else "В этот раз не вышло — очков не получено."
    return {"message": message, "points": result.points, "dev_points": result.dev_points}


@router.post("/extras")
async def post_extras(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    user = await _user(session, user_id)
    try:
        result = await train_extras(session, redis, user_id, user.phase)
    except TrainingOnCooldownError as exc:
        raise HTTPException(400, f"Тренировка ещё на кулдауне — через {format_countdown(exc.retry_after_seconds)}.")
    if result.attempted == 0:
        raise HTTPException(400, "Нечего тренировать — сначала заверби хотя бы одного статиста.")
    last = {"attempted": result.attempted, "stage1": result.stage1, "stage2": result.stage2, "stage3": result.stage3}
    await redis.set(last_extras_training(user_id), json.dumps(last), ex=LAST_EXTRAS_TTL_SECONDS)
    return {
        "message": f"Тренировка завершена: участвовало {format_number(result.attempted)}",
        "attempted": result.attempted,
        "stage1": result.stage1,
        "stage2": result.stage2,
        "stage3": result.stage3,
    }
