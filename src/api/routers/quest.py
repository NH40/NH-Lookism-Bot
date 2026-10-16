"""API-роутер Mini App: ежедневные задания (экран «Задания»).

Бизнес-логика — ТОЛЬКО через `bot.services.quest` / `bot.services.dev_quest` (те же сервисы,
что вызывает `bot.handlers.quest`); роутер валидирует ввод, мапит исключения в русские тексты.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from bot.config.quest import QUEST_SWAPS_PER_DAY, QUESTS_PER_DAY
from bot.constant.dev_quest import QUEST_CONVICTION, QUEST_SCHOOL, QUEST_TEACHER
from bot.services.battle_pass import scroll_count
from bot.services.dev_quest import NoScrollError, QuestNotSkippableError, skip_with_scroll, skippable
from bot.services.gang import get_gang
from bot.services.quest import (
    QuestAlreadyDoneError,
    QuestBusyError,
    QuestNotFoundError,
    RerollUsedError,
    get_status,
    reroll_all,
    swap,
)
from bot.texts.dev_quest import TASK_LABELS
from bot.texts.quest import (
    BUSY_ALERT,
    NO_SCROLL_ALERT,
    QUEST_DONE_ALERT,
    QUEST_GONE_ALERT,
    REROLLED_ALERT,
    REROLL_USED_ALERT,
    SCROLL_GONE_ALERT,
    SCROLL_QUEST_CONVICTION,
    SCROLL_QUEST_SCHOOL,
    SCROLL_QUEST_TEACHER,
    SCROLL_USED_ALERT,
)
from bot.texts.school import SCHOOL_NAMES
from bot.texts.unique_technique import TEACHER_NAMES

router = APIRouter(prefix="/api/quests", tags=["quests"])

_NOT_ONBOARDED = "Сначала создайте банду в боте (/start)."


class QuestOut(BaseModel):
    slot: int
    task: str
    label: str
    tier: int
    xp: int
    progress: int
    target: int
    done: bool


class SkippableOut(BaseModel):
    id: int
    label: str


class QuestsOut(BaseModel):
    quests: list[QuestOut]
    completed: int
    total: int
    next_multiplier: int
    full_reroll_available: bool
    swaps_left: int
    swaps_per_day: int
    resets_in: int
    scrolls: int
    skippable: list[SkippableOut]
    is_admin: bool = False  # тестовая кнопка «выполнить все задания»


class SwapIn(BaseModel):
    slot: int


class ScrollIn(BaseModel):
    quest_id: int


def _dev_quest_label(kind: str, ref: str) -> str:
    if kind == QUEST_TEACHER:
        return SCROLL_QUEST_TEACHER.format(name=TEACHER_NAMES.get(ref, ref))
    if kind == QUEST_SCHOOL:
        return SCROLL_QUEST_SCHOOL.format(name=SCHOOL_NAMES.get(ref, ref))
    return SCROLL_QUEST_CONVICTION if kind == QUEST_CONVICTION else kind


async def _guard(session: AsyncSession, user_id: int) -> None:
    if await get_gang(session, user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_ONBOARDED)


@router.get("", response_model=QuestsOut)
async def get_quests(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> QuestsOut:
    await _guard(session, user_id)
    st = await get_status(session, user_id)
    return QuestsOut(
        quests=[
            QuestOut(
                slot=q.slot, task=q.task, label=TASK_LABELS.get(q.task, q.task), tier=q.tier, xp=q.xp,
                progress=q.progress, target=q.target, done=q.done,
            )
            for q in st.quests
        ],
        completed=st.completed,
        total=QUESTS_PER_DAY,
        next_multiplier=st.next_multiplier,
        full_reroll_available=st.full_reroll_available,
        swaps_left=st.swaps_left,
        swaps_per_day=QUEST_SWAPS_PER_DAY,
        resets_in=st.resets_in,
        scrolls=await scroll_count(session, user_id),
        skippable=[
            SkippableOut(id=q.id, label=_dev_quest_label(q.kind, q.ref)) for q in await skippable(session, user_id)
        ],
        is_admin=await _is_admin(session, user_id),
    )


async def _is_admin(session: AsyncSession, user_id: int) -> bool:
    from bot.config.settings import get_settings
    from bot.services.admin.admin import is_admin

    return await is_admin(session, user_id, get_settings())


@router.post("/admin-complete")
async def post_admin_complete(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    """Тест для админов: выполнить все свои задания (права перепроверяет сервис)."""
    from bot.services.admin.testing import NotAdminError, complete_all_quests

    try:
        daily, dev = await complete_all_quests(session, user_id)
    except NotAdminError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Только для админов.")
    return {"message": f"Выполнено: ежедневных {daily}, квестов развития {dev}."}


@router.post("/reroll-all")
async def post_reroll_all(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await _guard(session, user_id)
    try:
        await reroll_all(session, redis, user_id)
    except QuestBusyError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, BUSY_ALERT)
    except RerollUsedError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, REROLL_USED_ALERT)
    return {"message": REROLLED_ALERT}


@router.post("/swap")
async def post_swap(
    body: SwapIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await _guard(session, user_id)
    try:
        await swap(session, redis, user_id, body.slot)
    except QuestBusyError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, BUSY_ALERT)
    except RerollUsedError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, REROLL_USED_ALERT)
    except QuestAlreadyDoneError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, QUEST_DONE_ALERT)
    except QuestNotFoundError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, QUEST_GONE_ALERT)
    return {"message": REROLLED_ALERT}


@router.post("/scroll")
async def post_scroll(
    body: ScrollIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _guard(session, user_id)
    try:
        await skip_with_scroll(session, user_id, body.quest_id)
    except NoScrollError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, NO_SCROLL_ALERT)
    except QuestNotSkippableError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, SCROLL_GONE_ALERT)
    return {"message": SCROLL_USED_ALERT}
