"""Родословная — выбор навсегда (хендлеры).

Экран выбора показывается шагом онбординга после названия банды и — тем, у кого
родословной ещё нет (зарегистрировались до её появления), — при `/start` и входе в
«📈 Развитие». `prompt_bloodline()` — публичная функция домена для этих мест.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.bloodline import LEVELS, bloodline_level_cost
from bot.config.development import MAX_LEVEL
from bot.db.repositories import donate as donate_repo
from bot.constant.bloodline import (
    BLOODLINES,
    CB_BLOODLINE2_CHOOSE_PREFIX,
    CB_BLOODLINE2_LEVEL_UP,
    CB_BLOODLINE2_SCREEN,
    CB_BLOODLINE2_LIST,
    CB_BLOODLINE_LEVEL_UP,
    CB_BLOODLINE_LIST,
    CB_BLOODLINE_PICK_PREFIX,
    CB_BLOODLINE_SCREEN,
    CB_BLOODLINE_VIEW_PREFIX,
)
from bot.keyboards.bloodline import choose2_menu, choose_menu, detail2_menu, detail_menu, view_menu
from bot.services.bloodline import (
    BloodlineAlreadyChosenError,
    BloodlineMaxLevelError,
    NoBloodlineError,
    NoSecondBodyError,
    NotEnoughBloodError,
    UnknownBloodlineError,
    choose,
    get_state,
    choose2,
    level_up,
    level_up2,
)
from bot.texts.development import describe_level
from bot.utils.formatting import format_number
from bot.texts.bloodline import (
    ALREADY_CHOSEN_ALERT,
    BLOODLINE_DESCRIPTIONS,
    BLOODLINE_NAMES,
    BLOODLINE_NO_DESCRIPTION,
    CHOOSE2_SCREEN,
    PICKED_ALERT,
    CHOOSE_SCREEN,
    NO_SECOND_BODY_ALERT,
    SECOND_LINE,
    BTN_BLOODLINE2_OPEN,
    SECOND_BODY_SUFFIX,
    DETAIL_SCREEN,
    LEVEL_LINE_DONE,
    LEVEL_LINE_LOCKED,
    LEVEL_UP_ALERT,
    MAX_LEVEL_ALERT,
    MAX_LEVEL_LINE,
    NEXT_LEVEL_LINE,
    NOT_ENOUGH_BLOOD_ALERT,
    SPECIAL_EFFECTS,
    PICKED,
    VIEW_SCREEN,
)
from bot.utils.safe_edit import safe_clear_markup, safe_edit_text

router = Router(name="bloodline")


async def prompt_bloodline(message: Message) -> None:
    await message.answer(CHOOSE_SCREEN, reply_markup=choose_menu())


@router.callback_query(F.data == CB_BLOODLINE_LIST)
async def cb_bloodline_list(callback: CallbackQuery) -> None:
    await callback.answer()
    await safe_edit_text(callback.message, CHOOSE_SCREEN, reply_markup=choose_menu())


@router.callback_query(F.data.startswith(CB_BLOODLINE_VIEW_PREFIX))
async def cb_bloodline_view(callback: CallbackQuery) -> None:
    code = callback.data.removeprefix(CB_BLOODLINE_VIEW_PREFIX)
    if code not in BLOODLINES:
        await callback.answer()
        return
    await callback.answer()
    await safe_edit_text(
        callback.message,
        VIEW_SCREEN.format(
            name=BLOODLINE_NAMES[code],
            description=BLOODLINE_DESCRIPTIONS.get(code, BLOODLINE_NO_DESCRIPTION),
            first=describe_level(LEVELS[code][0], SPECIAL_EFFECTS),
        ),
        reply_markup=view_menu(code),
    )


async def render_bloodline(session: AsyncSession, user_id: int):
    state = await get_state(session, user_id)
    levels = "\n".join(
        (LEVEL_LINE_DONE if n <= state.level else LEVEL_LINE_LOCKED).format(n=n, effect=describe_level(spec, SPECIAL_EFFECTS))
        for n, spec in enumerate(LEVELS[state.code], 1)
    )
    cost = state.next_cost
    text = DETAIL_SCREEN.format(
        name=BLOODLINE_NAMES[state.code],
        level=state.level,
        description=BLOODLINE_DESCRIPTIONS[state.code],
        levels=levels,
        drops=format_number(state.blood_drops),
        next_line=NEXT_LEVEL_LINE.format(cost=cost) if cost else MAX_LEVEL_LINE,
    )
    body = await donate_repo.body_state(session, user_id)
    if body is None or not body[0]:
        return text, detail_menu(cost)
    _second_body, _path2, _first, code2, level2, _drops = body
    if code2 is None:
        return text, detail_menu(cost, choose2=True)
    text += SECOND_LINE.format(name=BLOODLINE_NAMES[code2], level=level2, max_level=MAX_LEVEL)
    return text, detail_menu(cost, second_label=BTN_BLOODLINE2_OPEN.format(name=BLOODLINE_NAMES[code2], level=level2))


async def render_bloodline2(session: AsyncSession, user_id: int):
    """Уровни второй родословной (второе тело) — тот же вид, что у первой. None — её нет."""
    body = await donate_repo.body_state(session, user_id)
    if body is None or not body[0] or body[3] is None:
        return None
    _second_body, _path2, _first, code2, level2, _drops = body
    levels = "\n".join(
        (LEVEL_LINE_DONE if n <= level2 else LEVEL_LINE_LOCKED).format(n=n, effect=describe_level(spec, SPECIAL_EFFECTS))
        for n, spec in enumerate(LEVELS[code2], 1)
    )
    cost2 = bloodline_level_cost(level2 + 1) if level2 < MAX_LEVEL else None
    state = await get_state(session, user_id)
    text = DETAIL_SCREEN.format(
        name=BLOODLINE_NAMES[code2] + SECOND_BODY_SUFFIX, level=level2, description=BLOODLINE_DESCRIPTIONS[code2],
        levels=levels, drops=format_number(state.blood_drops if state else 0),
        next_line=NEXT_LEVEL_LINE.format(cost=cost2) if cost2 else MAX_LEVEL_LINE,
    )
    return text, detail2_menu(cost2)


@router.callback_query(F.data == CB_BLOODLINE2_SCREEN)
async def cb_bloodline2_screen(callback: CallbackQuery, session: AsyncSession) -> None:
    rendered = await render_bloodline2(session, callback.from_user.id)
    await callback.answer()
    text, markup = rendered if rendered is not None else await render_bloodline(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_BLOODLINE_SCREEN)
async def cb_bloodline_screen(callback: CallbackQuery, session: AsyncSession) -> None:
    state = await get_state(session, callback.from_user.id)
    if state is None or state.code is None:
        await callback.answer()
        await prompt_bloodline(callback.message)
        return
    await callback.answer()
    text, markup = await render_bloodline(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_BLOODLINE_LEVEL_UP)
async def cb_bloodline_level_up(callback: CallbackQuery, session: AsyncSession) -> None:
    # Popup-тексты — без HTML.
    try:
        level = await level_up(session, callback.from_user.id)
    except NoBloodlineError:
        await callback.answer()
        return
    except BloodlineMaxLevelError:
        await callback.answer(MAX_LEVEL_ALERT, show_alert=True)
        return
    except NotEnoughBloodError as exc:
        await callback.answer(NOT_ENOUGH_BLOOD_ALERT.format(cost=exc.cost, have=exc.have), show_alert=True)
        return
    await callback.answer(LEVEL_UP_ALERT.format(level=level))
    text, markup = await render_bloodline(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_BLOODLINE_PICK_PREFIX))
async def cb_bloodline_pick(callback: CallbackQuery, session: AsyncSession) -> None:
    # Отложенный импорт: профиль импортирует этот домен (строка родословной), а тут после
    # выбора показываем профиль — без него был бы круговой импорт хендлеров.
    from bot.handlers.profile import show_profile

    code = callback.data.removeprefix(CB_BLOODLINE_PICK_PREFIX)
    try:
        await choose(session, callback.from_user.id, code)
    except UnknownBloodlineError:
        await callback.answer()
        return
    except BloodlineAlreadyChosenError:
        # Родословная уже есть (выбор навсегда, переживает удаление банды) — не тупик: убираем
        # старые кнопки и ведём дальше в профиль. Popup — без HTML.
        await callback.answer(ALREADY_CHOSEN_ALERT, show_alert=True)
        await safe_clear_markup(callback.message)
        await show_profile(callback.message, session, callback.from_user.id)
        return
    await callback.answer()
    await safe_clear_markup(callback.message)
    await callback.message.answer(PICKED.format(name=BLOODLINE_NAMES[code]))
    await show_profile(callback.message, session, callback.from_user.id)


@router.callback_query(F.data == CB_BLOODLINE2_LIST)
async def cb_bloodline2_list(callback: CallbackQuery, session: AsyncSession) -> None:
    body = await donate_repo.body_state(session, callback.from_user.id)
    if body is None or not body[0]:
        await callback.answer(NO_SECOND_BODY_ALERT, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, CHOOSE2_SCREEN, reply_markup=choose2_menu(body[2]))


@router.callback_query(F.data.startswith(CB_BLOODLINE2_CHOOSE_PREFIX))
async def cb_bloodline2_choose(callback: CallbackQuery, session: AsyncSession) -> None:
    code = callback.data.removeprefix(CB_BLOODLINE2_CHOOSE_PREFIX)
    # Popup-тексты — без HTML.
    try:
        await choose2(session, callback.from_user.id, code)
    except UnknownBloodlineError:
        await callback.answer()
        return
    except NoSecondBodyError:
        await callback.answer(NO_SECOND_BODY_ALERT, show_alert=True)
        return
    except BloodlineAlreadyChosenError:
        await callback.answer(ALREADY_CHOSEN_ALERT, show_alert=True)
        return
    await callback.answer(PICKED_ALERT.format(name=BLOODLINE_NAMES[code]))
    text, markup = await render_bloodline(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_BLOODLINE2_LEVEL_UP)
async def cb_bloodline2_level_up(callback: CallbackQuery, session: AsyncSession) -> None:
    # Popup-тексты — без HTML.
    try:
        level = await level_up2(session, callback.from_user.id)
    except NoBloodlineError:
        await callback.answer()
        return
    except BloodlineMaxLevelError:
        await callback.answer(MAX_LEVEL_ALERT, show_alert=True)
        return
    except NotEnoughBloodError as exc:
        await callback.answer(NOT_ENOUGH_BLOOD_ALERT.format(cost=exc.cost, have=exc.have), show_alert=True)
        return
    await callback.answer(LEVEL_UP_ALERT.format(level=level))
    rendered = await render_bloodline2(session, callback.from_user.id)
    text, markup = rendered if rendered is not None else await render_bloodline(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)
