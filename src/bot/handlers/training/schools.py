"""Школы статистов в тренировках — занятия у купленных учителей (хендлеры).

Пользователь 2026-10-13: «кнопку тренировки школ статистов — чтобы качали не в магазине, а тут».
Покупка учителя осталась в 🛍 Магазине → Обучение, занятия — здесь. Логика — `services/school`.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.school import (
    SCHOOL_COVERAGE_PERCENT,
    SCHOOL_JOIN_PERCENT,
    SCHOOL_LESSON_PRICE,
    SCHOOL_LEVEL_UP_PERCENT,
    SCHOOL_MAX_LEVEL,
    SCHOOL_TEACHER_PRICE,
)
from bot.constant.school import SCHOOLS
from bot.constant.training import CB_TRAIN_SCHOOL_LESSON_PREFIX, CB_TRAIN_SCHOOLS_OPEN
from bot.keyboards.training import schools_menu
from bot.services.gang import get_gang
from bot.services.school import (
    LessonOnCooldownError,
    NoStudentsError,
    NotEnoughCoinsError,
    TeacherNotOwnedError,
    lesson,
    shop_teachers,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.school import (
    COOLDOWN_ALERT,
    LESSON_DONE,
    NO_STUDENTS_ALERT,
    NOT_ENOUGH_ALERT,
    NOT_OWNED_ALERT,
    SCHOOL_EFFECTS,
    SCHOOL_NAMES,
    SCHOOL_TEACHERS,
)
from bot.texts.training import (
    BTN_SCHOOL_LESSON,
    BTN_SCHOOL_LESSON_CD,
    SCHOOL_COOLDOWN,
    SCHOOL_LINE_LOCKED,
    SCHOOL_LINE_OWNED,
    SCHOOL_LINE_UNLOCKED,
    SCHOOLS_SCREEN,
)
from bot.utils.formatting import format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="training_schools")


async def render_schools(session: AsyncSession, redis: Redis, user_id: int):
    teachers = {t.school: t for t in await shop_teachers(session, redis, user_id)}
    lines, buttons = [], []
    for school in SCHOOLS:
        name, title = SCHOOL_TEACHERS[school], SCHOOL_NAMES[school]
        t = teachers.get(school)
        if t is not None and t.owned:
            cd = SCHOOL_COOLDOWN.format(countdown=format_countdown(t.cooldown)) if t.cooldown else ""
            lines.append(SCHOOL_LINE_OWNED.format(teacher=name, school=title, effect=SCHOOL_EFFECTS[school], cooldown=cd))
            label = (
                BTN_SCHOOL_LESSON_CD.format(teacher=name, countdown=format_countdown(t.cooldown)) if t.cooldown
                else BTN_SCHOOL_LESSON.format(teacher=name, price=format_number(SCHOOL_LESSON_PRICE))
            )
            buttons.append((school, label))
        elif t is not None:
            lines.append(SCHOOL_LINE_UNLOCKED.format(teacher=name, school=title, price=format_number(SCHOOL_TEACHER_PRICE)))
        else:
            lines.append(SCHOOL_LINE_LOCKED.format(teacher=name, school=title))
    text = SCHOOLS_SCREEN.format(
        price=format_number(SCHOOL_LESSON_PRICE), coverage=SCHOOL_COVERAGE_PERCENT, join=SCHOOL_JOIN_PERCENT,
        level_up=SCHOOL_LEVEL_UP_PERCENT, max_level=SCHOOL_MAX_LEVEL, lines="\n".join(lines),
    )
    return text, schools_menu(buttons)


@router.callback_query(F.data == CB_TRAIN_SCHOOLS_OPEN)
async def cb_schools(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    text, markup = await render_schools(session, redis, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_TRAIN_SCHOOL_LESSON_PREFIX))
async def cb_school_lesson(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    school = callback.data.removeprefix(CB_TRAIN_SCHOOL_LESSON_PREFIX)
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
    # Popup — без HTML.
    done = LESSON_DONE.format(
        teacher=SCHOOL_TEACHERS[school], school=SCHOOL_NAMES[school],
        joined=format_number(result.joined), leveled=format_number(result.leveled),
    )
    await callback.answer(done.replace("<b>", "").replace("</b>", ""), show_alert=True)
    text, markup = await render_schools(session, redis, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)
