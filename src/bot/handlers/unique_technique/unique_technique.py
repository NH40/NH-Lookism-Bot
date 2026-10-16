"""Уникальные техники и учителя на карте (хендлеры).

Учитель — событие на карте: экран открывается его меткой (`handlers/event` делегирует сюда
`render_teacher`), «🤝 Законнектиться» — квест. Техники и квесты — «📈 Развитие → 🥋
Уникальные техники». `teacher_push_text()` — текст пуша о появлении учителя (`main.py`).
"""
from __future__ import annotations

from bot.services.unique_technique import TrainingRequiredError
from bot.texts.training import TECH_NEED_TRAINING_ALERT
from bot.keyboards.common import back_menu

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.unique_technique import LEVELS, TEACHER_QUESTS
from bot.constant.event import CB_EVENT_CONNECT_PREFIX, EVENT_TEACHER
from bot.constant.unique_technique import (
    CB_TECH_ACTIVATE_PREFIX,
    CB_TECH_CLAIM_PREFIX,
    CB_TECH_LEVEL_UP_PREFIX,
    CB_TECH_OPEN,
    CB_TECH_VIEW_PREFIX,
)
from bot.keyboards.unique_technique import teacher_menu, technique_detail_menu, techniques_menu
from bot.services.gang import get_gang
from bot.services.unique_technique import (
    NotEnoughFragmentsError,
    QuestAlreadyActiveError,
    QuestNotCompleteError,
    SwapOnCooldownError,
    TeacherGoneError,
    TechniqueMaxLevelError,
    TechniqueNotOwnedError,
    TechniqueOwnedError,
    UnknownTechniqueError,
    activate,
    claim_teacher_quest,
    connect,
    get_teacher,
    get_view,
    level_up,
)
from bot.texts.dev_quest import render_tasks
from bot.texts.development import describe_level
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.unique_technique import (
    ACTIVATED_ALERT,
    CLAIMED,
    CONNECTED,
    DETAIL_ACTIVE,
    LEVEL_LINE_DONE,
    LEVEL_LINE_LOCKED,
    LEVEL_UP_ALERT,
    MARK_ACTIVE,
    MARK_OWNED,
    MAX_LEVEL_ALERT,
    MAX_LEVEL_LINE,
    NEXT_LEVEL_LINE,
    NO_TECHNIQUES,
    NOT_ENOUGH_ALERT,
    NOT_OWNED_ALERT,
    OWNED_LINE,
    PUSH_TEACHER,
    QUEST_ACTIVE_ALERT,
    QUEST_BLOCK,
    QUEST_NOT_DONE_ALERT,
    QUESTS_HEADER,
    SPECIAL_EFFECTS,
    SWAP_COOLDOWN_ALERT,
    TEACHER_GONE_ALERT,
    TEACHER_NAMES,
    TEACHER_OFFER,
    TEACHER_OWNED,
    TEACHER_QUEST,
    TEACHER_QUEST_DONE,
    TEACHER_SCREEN,
    TECHNIQUE_DETAIL,
    TECHNIQUE_NAMES,
    TECHNIQUE_OWNED_ALERT,
    TECHNIQUE_THEMES,
    TECHNIQUES_SCREEN,
)
from bot.utils.formatting import format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="unique_technique")


def teacher_push_text(event) -> str | None:
    """Текст пуша о появлении учителя на карте (событие `teacher`)."""
    if event.kind != EVENT_TEACHER:
        return None
    return PUSH_TEACHER.format(
        teacher=TEACHER_NAMES[event.code],
        duration=format_countdown(event.duration_seconds),
        technique=TECHNIQUE_NAMES[event.code],
    )


async def render_teacher(session: AsyncSession, user_id: int, event_id: int):
    view = await get_teacher(session, user_id, event_id)
    if view.owned:
        body = TEACHER_OWNED
    elif view.quest is not None:
        body = TEACHER_QUEST.format(tasks=render_tasks(view.quest.tasks, view.quest.progress))
        if view.quest.complete:
            body += TEACHER_QUEST_DONE
    else:
        body = TEACHER_OFFER + "\n\n" + TEACHER_QUEST.format(tasks=render_tasks(TEACHER_QUESTS[view.code], {}))
    text = TEACHER_SCREEN.format(
        teacher=TEACHER_NAMES[view.code],
        technique=TECHNIQUE_NAMES[view.code],
        theme=TECHNIQUE_THEMES[view.code],
        body=body,
        countdown=format_countdown(view.ends_in_seconds),
    )
    markup = teacher_menu(
        view.event_id, view.code,
        can_connect=not view.owned and view.quest is None,
        can_claim=view.quest is not None and view.quest.complete,
    )
    return text, markup


async def render_techniques(session: AsyncSession, redis: Redis, user_id: int):
    view = await get_view(session, redis, user_id)
    owned = "\n".join(
        OWNED_LINE.format(mark=MARK_ACTIVE if c == view.active else MARK_OWNED, name=TECHNIQUE_NAMES[c], level=lv)
        for c, lv in view.owned.items()
    ) or NO_TECHNIQUES
    quests = ""
    if view.quests:
        quests = QUESTS_HEADER + "".join(
            QUEST_BLOCK.format(technique=TECHNIQUE_NAMES[q.ref], teacher=TEACHER_NAMES[q.ref], tasks=render_tasks(q.tasks, q.progress))
            for q in view.quests
        )
    text = TECHNIQUES_SCREEN.format(
        active=TECHNIQUE_NAMES.get(view.active, "—"), fragments=format_number(view.fragments), owned=owned, quests=quests
    )
    claimable = [q.ref for q in view.quests if q.complete]
    return text, techniques_menu(view.owned, view.active, claimable)


async def _render_detail(session: AsyncSession, redis: Redis, user_id: int, code: str):
    view = await get_view(session, redis, user_id)
    level = view.owned[code]
    levels = "\n".join(
        (LEVEL_LINE_DONE if n <= level else LEVEL_LINE_LOCKED).format(n=n, effect=describe_level(spec, SPECIAL_EFFECTS))
        for n, spec in enumerate(LEVELS[code], 1)
    )
    cost = view.next_costs[code]
    text = TECHNIQUE_DETAIL.format(
        name=TECHNIQUE_NAMES[code],
        level=level,
        active=DETAIL_ACTIVE if code == view.active else "",
        theme=TECHNIQUE_THEMES[code],
        levels=levels,
        next_line=NEXT_LEVEL_LINE.format(cost=format_number(cost), have=format_number(view.fragments)) if cost else MAX_LEVEL_LINE,
    )
    return text, technique_detail_menu(code, cost=cost, is_active=code == view.active)


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


@router.callback_query(F.data.startswith(CB_EVENT_CONNECT_PREFIX))
async def cb_teacher_connect(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    raw = callback.data.removeprefix(CB_EVENT_CONNECT_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    # Popup-тексты — без HTML.
    try:
        quest = await connect(session, callback.from_user.id, int(raw))
    except TeacherGoneError:
        await callback.answer(TEACHER_GONE_ALERT, show_alert=True)
        return
    except TechniqueOwnedError:
        await callback.answer(TECHNIQUE_OWNED_ALERT, show_alert=True)
        return
    except QuestAlreadyActiveError:
        await callback.answer(QUEST_ACTIVE_ALERT, show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        CONNECTED.format(teacher=TEACHER_NAMES[quest.ref], tasks=render_tasks(quest.tasks, quest.progress))
    , reply_markup=back_menu(CB_TECH_OPEN))


@router.callback_query(F.data.startswith(CB_TECH_CLAIM_PREFIX))
async def cb_technique_claim(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    code = callback.data.removeprefix(CB_TECH_CLAIM_PREFIX)
    try:
        await claim_teacher_quest(session, callback.from_user.id, code)
    except (UnknownTechniqueError, QuestNotCompleteError):
        await callback.answer(QUEST_NOT_DONE_ALERT, show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(CLAIMED.format(teacher=TEACHER_NAMES[code], technique=TECHNIQUE_NAMES[code]))
    text, markup = await render_techniques(session, redis, callback.from_user.id)
    await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data == CB_TECH_OPEN)
async def cb_techniques_open(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    text, markup = await render_techniques(session, redis, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_TECH_VIEW_PREFIX))
async def cb_technique_view(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    code = callback.data.removeprefix(CB_TECH_VIEW_PREFIX)
    view = await get_view(session, redis, callback.from_user.id)
    if code not in view.owned:
        await callback.answer(NOT_OWNED_ALERT, show_alert=True)
        return
    await callback.answer()
    text, markup = await _render_detail(session, redis, callback.from_user.id, code)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_TECH_ACTIVATE_PREFIX))
async def cb_technique_activate(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    code = callback.data.removeprefix(CB_TECH_ACTIVATE_PREFIX)
    try:
        await activate(session, redis, callback.from_user.id, code)
    except TechniqueNotOwnedError:
        await callback.answer(NOT_OWNED_ALERT, show_alert=True)
        return
    except SwapOnCooldownError as exc:
        await callback.answer(SWAP_COOLDOWN_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
        return
    await callback.answer(ACTIVATED_ALERT.format(name=TECHNIQUE_NAMES[code]))
    text, markup = await _render_detail(session, redis, callback.from_user.id, code)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_TECH_LEVEL_UP_PREFIX))
async def cb_technique_level_up(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    code = callback.data.removeprefix(CB_TECH_LEVEL_UP_PREFIX)
    try:
        level = await level_up(session, callback.from_user.id, code)
    except TechniqueNotOwnedError:
        await callback.answer(NOT_OWNED_ALERT, show_alert=True)
        return
    except TechniqueMaxLevelError:
        await callback.answer(MAX_LEVEL_ALERT, show_alert=True)
        return
    except NotEnoughFragmentsError as exc:
        await callback.answer(NOT_ENOUGH_ALERT.format(cost=exc.cost, have=exc.have), show_alert=True)
        return
    except TrainingRequiredError:
        await callback.answer(TECH_NEED_TRAINING_ALERT, show_alert=True)
        return
    await callback.answer(LEVEL_UP_ALERT.format(name=TECHNIQUE_NAMES[code], level=level))
    text, markup = await _render_detail(session, redis, callback.from_user.id, code)
    await safe_edit_text(callback.message, text, reply_markup=markup)
