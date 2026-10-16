"""Учителя статистов — экран учителя на карте, задание, покупка и занятия (хендлеры).

Экран учителя открывается его меткой на карте (`handlers/event` делегирует сюда
`render_school_teacher`); покупка и занятия — раздел «📚 Обучение» в магазине
(`handlers/shop` собирает его через `render_shop_block`).
"""
from __future__ import annotations

from bot.keyboards.common import back_menu
from bot.constant.map import CB_MAP_OPEN
from bot.constant.school import CB_SCHOOL_OPEN

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.school import SCHOOL_LESSON_PRICE, SCHOOL_QUESTS, SCHOOL_TEACHER_PRICE
from bot.constant.event import EVENT_SCHOOL_TEACHER
from bot.constant.school import CB_SCHOOL_BUY_PREFIX, CB_SCHOOL_CLAIM_PREFIX, CB_SCHOOL_MEET_PREFIX, CB_SCHOOL_TRAIN_PREFIX
from bot.keyboards.school import shop_rows, teacher_menu
from bot.services.gang import get_gang
from bot.services.school import (
    AlreadyUnlockedError,
    LessonOnCooldownError,
    NoStudentsError,
    NotEnoughCoinsError,
    QuestAlreadyActiveError,
    QuestNotCompleteError,
    SchoolBusyError,
    TeacherAlreadyOwnedError,
    TeacherGoneError,
    TeacherNotOwnedError,
    TeacherNotUnlockedError,
    UnknownSchoolError,
    buy_teacher,
    claim_quest,
    get_teacher,
    lesson,
    meet,
    quests,
    shop_teachers,
)
from bot.texts.dev_quest import render_tasks
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.school import (
    ALREADY_UNLOCKED_ALERT,
    BOUGHT_ALERT,
    BUSY_ALERT,
    CLAIMED,
    COOLDOWN_ALERT,
    LESSON_DONE,
    MET,
    NO_STUDENTS_ALERT,
    NOT_ENOUGH_ALERT,
    NOT_OWNED_ALERT,
    PUSH_TEACHER,
    QUEST_ACTIVE_ALERT,
    QUEST_NOT_DONE_ALERT,
    SCHOOL_EFFECTS,
    SCHOOL_NAMES,
    SCHOOL_TEACHERS,
    SHOP_BLOCK,
    SHOP_COOLDOWN,
    SHOP_EMPTY,
    SHOP_LINE_LOCKED,
    SHOP_LINE_OWNED,
    SHOP_QUEST_LINE,
    TEACHER_GONE_ALERT,
    TEACHER_OFFER,
    TEACHER_QUEST,
    TEACHER_QUEST_DONE,
    TEACHER_SCREEN,
    TEACHER_UNLOCKED,
    BTN_SCHOOL_EVENT,
)
from bot.utils.formatting import format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="school")


def school_button_label(event) -> str:
    return BTN_SCHOOL_EVENT.format(teacher=SCHOOL_TEACHERS[event.code], school=SCHOOL_NAMES[event.code])


def school_push_text(event) -> str | None:
    if event.kind != EVENT_SCHOOL_TEACHER:
        return None
    return PUSH_TEACHER.format(
        teacher=SCHOOL_TEACHERS[event.code], school=SCHOOL_NAMES[event.code], duration=format_countdown(event.duration_seconds)
    )


async def render_school_teacher(session: AsyncSession, user_id: int, event_id: int):
    view = await get_teacher(session, user_id, event_id)
    if view.unlocked:
        body = TEACHER_UNLOCKED
    elif view.quest is not None:
        body = TEACHER_QUEST.format(tasks=render_tasks(view.quest.tasks, view.quest.progress))
        if view.quest.complete:
            body += TEACHER_QUEST_DONE
    else:
        body = TEACHER_OFFER.format(tasks=render_tasks(SCHOOL_QUESTS[view.school], {}))
    text = TEACHER_SCREEN.format(
        teacher=SCHOOL_TEACHERS[view.school], school=SCHOOL_NAMES[view.school], effect=SCHOOL_EFFECTS[view.school],
        body=body, countdown=format_countdown(view.ends_in_seconds),
    )
    markup = teacher_menu(
        view.event_id, view.school,
        can_meet=not view.unlocked and view.quest is None,
        can_claim=view.quest is not None and view.quest.complete,
    )
    return text, markup


async def render_shop_block(session: AsyncSession, redis: Redis, user_id: int):
    """Раздел «📚 Обучение» магазина: строки текста и кнопки."""
    teachers = await shop_teachers(session, redis, user_id)
    active = await quests(session, user_id)
    lines = ""
    for t in teachers:
        name, school = SCHOOL_TEACHERS[t.school], SCHOOL_NAMES[t.school]
        if t.owned:
            cooldown = SHOP_COOLDOWN.format(countdown=format_countdown(t.cooldown)) if t.cooldown else ""
            lines += SHOP_LINE_OWNED.format(teacher=name, school=school, price=format_number(SCHOOL_LESSON_PRICE), cooldown=cooldown)
        else:
            lines += SHOP_LINE_LOCKED.format(teacher=name, school=school, price=format_number(SCHOOL_TEACHER_PRICE))
    for q in active:
        done = sum(min(q.progress.get(t, 0), n) for t, n in q.tasks.items())
        lines += SHOP_QUEST_LINE.format(teacher=SCHOOL_TEACHERS[q.ref], done=f"{done}/{sum(q.tasks.values())}")
    text = SHOP_BLOCK.format(lines=lines or SHOP_EMPTY)
    return text, shop_rows(teachers, [q.ref for q in active if q.complete])


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


@router.callback_query(F.data.startswith(CB_SCHOOL_MEET_PREFIX))
async def cb_school_meet(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    raw = callback.data.removeprefix(CB_SCHOOL_MEET_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    # Popup-тексты — без HTML.
    try:
        quest = await meet(session, callback.from_user.id, int(raw))
    except TeacherGoneError:
        await callback.answer(TEACHER_GONE_ALERT, show_alert=True)
        return
    except AlreadyUnlockedError:
        await callback.answer(ALREADY_UNLOCKED_ALERT, show_alert=True)
        return
    except QuestAlreadyActiveError:
        await callback.answer(QUEST_ACTIVE_ALERT, show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(MET.format(teacher=SCHOOL_TEACHERS[quest.ref], tasks=render_tasks(quest.tasks, quest.progress)), reply_markup=back_menu(CB_MAP_OPEN))


@router.callback_query(F.data.startswith(CB_SCHOOL_CLAIM_PREFIX))
async def cb_school_claim(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    school = callback.data.removeprefix(CB_SCHOOL_CLAIM_PREFIX)
    try:
        await claim_quest(session, callback.from_user.id, school)
    except (UnknownSchoolError, QuestNotCompleteError):
        await callback.answer(QUEST_NOT_DONE_ALERT, show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(CLAIMED.format(teacher=SCHOOL_TEACHERS[school]), reply_markup=back_menu(CB_SCHOOL_OPEN))


@router.callback_query(F.data.startswith(CB_SCHOOL_BUY_PREFIX))
async def cb_school_buy(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    school = callback.data.removeprefix(CB_SCHOOL_BUY_PREFIX)
    try:
        await buy_teacher(session, redis, callback.from_user.id, school)
    except SchoolBusyError:
        await callback.answer(BUSY_ALERT)
        return
    except (TeacherNotUnlockedError, TeacherAlreadyOwnedError):
        await callback.answer()
        return
    except NotEnoughCoinsError as exc:
        await callback.answer(NOT_ENOUGH_ALERT.format(cost=format_number(exc.cost)), show_alert=True)
        return
    await callback.answer(BOUGHT_ALERT.format(teacher=SCHOOL_TEACHERS[school]), show_alert=True)
    await _refresh_shop(callback, session, redis)


@router.callback_query(F.data.startswith(CB_SCHOOL_TRAIN_PREFIX))
async def cb_school_lesson(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    school = callback.data.removeprefix(CB_SCHOOL_TRAIN_PREFIX)
    try:
        result = await lesson(session, redis, callback.from_user.id, school)
    except TeacherNotOwnedError:
        await callback.answer(NOT_OWNED_ALERT, show_alert=True)
        return
    except NoStudentsError:
        await callback.answer(NO_STUDENTS_ALERT, show_alert=True)
        return
    except LessonOnCooldownError as exc:
        await callback.answer(COOLDOWN_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
        return
    except NotEnoughCoinsError as exc:
        await callback.answer(NOT_ENOUGH_ALERT.format(cost=format_number(exc.cost)), show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        LESSON_DONE.format(
            teacher=SCHOOL_TEACHERS[school], school=SCHOOL_NAMES[school],
            joined=format_number(result.joined), leveled=format_number(result.leveled),
        )
    , reply_markup=back_menu(CB_SCHOOL_OPEN))
    await _refresh_shop(callback, session, redis)


async def _refresh_shop(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    from bot.handlers.shop import render_shop

    text, markup = await render_shop(session, redis, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_SCHOOL_OPEN)
async def cb_school_open(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    """«◀️ Назад» под итогом занятия / получения учителя — к магазину, где живут учителя (до
    2026-10-12 у этой кнопки не было обработчика, она молчала)."""
    from bot.handlers.shop import render_shop

    await callback.answer()
    text, markup = await render_shop(session, redis, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)
