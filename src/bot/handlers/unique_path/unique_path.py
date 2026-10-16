"""Путь — убеждение, пробуждение за фрагменты, уровни за очки пути, переключение (хендлеры).

Вход — «🛤 Путь» на экране «📈 Развитие». `notify_conviction()` — публичная функция домена:
проверка «подтверждения убеждений» после вложения очков в характеристики
(`handlers/profile/stats.py`) и при открытии «Развития».
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.unique_path import TRAINING_KPD_CAP_PER_LEVEL
from bot.constant.unique_path import PATH_TRAINING
from bot.services.build import get_build
from bot.texts.unique_path import TRAINING_KPD_LINE
from bot.config.unique_path import LEVELS, PATH_AWAKEN_FRAGMENTS
from bot.constant.unique_path import (
    CB_PATH_ACTIVATE2_PREFIX,
    CB_PATH_ACTIVATE_PREFIX,
    CB_PATH_AWAKEN_PREFIX,
    CB_PATH_LEVEL_UP2,
    PATH_AWAKEN_RANDOM,
    CB_PATH_CLAIM_CONVICTION,
    CB_PATH_CLAIM_PATH,
    CB_PATH_LEVEL_UP,
    CB_PATH_OPEN,
    PATH_STAGE_CALLED,
    PATH_STAGE_CONVICTION,
    PATH_STAGE_NONE,
)
from bot.keyboards.unique_path import awaken_choice_menu, path_menu
from bot.services.gang import get_gang
from bot.services.unique_path import (
    NoSecondBodyError,
    NotEnoughFragmentsError,
    NotEnoughPointsError,
    PathMaxLevelError,
    PathNotOwnedError,
    QuestNotCompleteError,
    SwapOnCooldownError,
    WrongStageError,
    activate,
    activate2,
    check_conviction,
    claim_conviction,
    awaken_path,
    get_view,
    level_up,
)
from bot.texts.dev_quest import render_tasks
from bot.texts.development import describe_level
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.unique_path import (
    ACTIVATED_ALERT,
    AWAKEN_CHOICE_SCREEN,
    NO_SECOND_BODY_ALERT,
    SECOND_PATH_LINE,
    SECOND_PATH_NONE,
    CONVICTION_DONE,
    CONVICTION_PUSH,
    LEVEL_LINE_DONE,
    LEVEL_LINE_LOCKED,
    LEVEL_UP_ALERT,
    MAX_LEVEL_ALERT,
    MAX_LEVEL_LINE,
    NEXT_LEVEL_LINE,
    NOT_ENOUGH_ALERT,
    NOT_ENOUGH_FRAGMENTS_ALERT,
    NOT_OWNED_ALERT,
    OWNED_LINE,
    PATH_AWAKENED,
    PATH_NAMES,
    PATH_SCREEN,
    PATH_THEMES,
    QUEST_NOT_DONE_ALERT,
    SPECIAL_EFFECTS,
    STAGE_CALLED,
    STAGE_CONVICTION,
    STAGE_NONE,
    SWAP_COOLDOWN_ALERT,
    WRONG_STAGE_ALERT,
)
from bot.utils.formatting import format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="unique_path")


async def notify_conviction(message: Message, session: AsyncSession, user_id: int) -> None:
    """Проверить «подтверждение убеждений» и, если пришло, сообщить игроку."""
    if await check_conviction(session, user_id):
        await message.answer(CONVICTION_PUSH)


async def render_path(session: AsyncSession, redis: Redis, user_id: int):
    await check_conviction(session, user_id)
    view = await get_view(session, redis, user_id)
    if view.stage == PATH_STAGE_NONE:
        return (
            STAGE_NONE.format(rank_sum=view.rank_sum, rank_needed=view.rank_needed, awaken_cost=view.awaken_cost),
            path_menu(),
        )
    if view.stage == PATH_STAGE_CALLED:
        tasks = render_tasks(view.quest.tasks, view.quest.progress) if view.quest else "—"
        return STAGE_CALLED.format(tasks=tasks), path_menu(claim_conviction=bool(view.quest and view.quest.complete))
    if view.stage == PATH_STAGE_CONVICTION:
        text = STAGE_CONVICTION.format(fragments=format_number(view.fragments), awaken_cost=format_number(view.awaken_cost))
        return text, path_menu(awaken_cost=view.awaken_cost if view.fragments >= view.awaken_cost else None)
    level = view.owned.get(view.active, 0)
    levels = "\n".join(
        (LEVEL_LINE_DONE if n <= level else LEVEL_LINE_LOCKED).format(n=n, effect=describe_level(spec, SPECIAL_EFFECTS))
        for n, spec in enumerate(LEVELS[view.active], 1)
    )
    others = [c for c in view.owned if c != view.active]
    text = PATH_SCREEN.format(
        name=PATH_NAMES[view.active],
        level=level,
        theme=PATH_THEMES[view.active],
        levels=levels,
        points=format_number(view.points),
        next_line=NEXT_LEVEL_LINE.format(cost=format_number(view.next_cost)) if view.next_cost else MAX_LEVEL_LINE,
        owned_line=OWNED_LINE.format(paths=", ".join(PATH_NAMES[c] for c in others)) if others else "",
    )
    if PATH_TRAINING in (view.active, view.active2):
        kpd = (await get_build(session, user_id)).training_kpd
        text += TRAINING_KPD_LINE.format(p=round(kpd * 100), cap=round(view.owned.get(PATH_TRAINING, 0) * TRAINING_KPD_CAP_PER_LEVEL * 100))
    others2: list[str] = []
    if view.second_body:
        if view.active2:
            text += SECOND_PATH_LINE.format(name=PATH_NAMES[view.active2], level=view.owned.get(view.active2, 0))
        else:
            text += SECOND_PATH_NONE
        others2 = [c for c in others if c != view.active2]
    return text, path_menu(
        cost=view.next_cost, others=others,
        cost2=view.next_cost2 if view.active2 else None, others2=others2,
    )


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


@router.callback_query(F.data == CB_PATH_OPEN)
async def cb_path_open(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    text, markup = await render_path(session, redis, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_PATH_CLAIM_CONVICTION)
async def cb_path_conviction(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    try:
        await claim_conviction(session, callback.from_user.id)
    except (QuestNotCompleteError, WrongStageError):
        await callback.answer(QUEST_NOT_DONE_ALERT, show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(CONVICTION_DONE.format(awaken_cost=PATH_AWAKEN_FRAGMENTS))
    text, markup = await render_path(session, redis, callback.from_user.id)
    await callback.message.answer(text, reply_markup=markup)


async def _awaken(callback: CallbackQuery, session: AsyncSession, redis: Redis, choice: str | None) -> None:
    # Popup-тексты — без HTML.
    try:
        code = await awaken_path(session, callback.from_user.id, choice=choice)
    except WrongStageError:
        await callback.answer(WRONG_STAGE_ALERT, show_alert=True)
        return
    except PathNotOwnedError:
        await callback.answer(NOT_OWNED_ALERT, show_alert=True)
        return
    except NotEnoughFragmentsError as exc:
        await callback.answer(NOT_ENOUGH_FRAGMENTS_ALERT.format(cost=exc.cost, have=exc.have), show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(PATH_AWAKENED.format(name=PATH_NAMES[code], theme=PATH_THEMES[code]))
    text, markup = await render_path(session, redis, callback.from_user.id)
    await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data == CB_PATH_CLAIM_PATH)
async def cb_path_claim(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    view = await get_view(session, redis, callback.from_user.id)
    if view.bought:
        await callback.answer()
        await safe_edit_text(callback.message, AWAKEN_CHOICE_SCREEN, reply_markup=awaken_choice_menu(view.bought))
        return
    await _awaken(callback, session, redis, None)


@router.callback_query(F.data.startswith(CB_PATH_AWAKEN_PREFIX))
async def cb_path_awaken_choice(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    code = callback.data.removeprefix(CB_PATH_AWAKEN_PREFIX)
    await _awaken(callback, session, redis, None if code == PATH_AWAKEN_RANDOM else code)


@router.callback_query(F.data == CB_PATH_LEVEL_UP)
async def cb_path_level_up(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    await _level_up(callback, session, redis, 1)


@router.callback_query(F.data == CB_PATH_LEVEL_UP2)
async def cb_path_level_up2(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    await _level_up(callback, session, redis, 2)


async def _level_up(callback: CallbackQuery, session: AsyncSession, redis: Redis, slot: int) -> None:
    if not await _guard(callback, session):
        return
    # Popup-тексты — без HTML.
    try:
        level = await level_up(session, callback.from_user.id, slot=slot)
    except NoSecondBodyError:
        await callback.answer(NO_SECOND_BODY_ALERT, show_alert=True)
        return
    except PathNotOwnedError:
        await callback.answer(NOT_OWNED_ALERT, show_alert=True)
        return
    except PathMaxLevelError:
        await callback.answer(MAX_LEVEL_ALERT, show_alert=True)
        return
    except NotEnoughPointsError as exc:
        await callback.answer(NOT_ENOUGH_ALERT.format(cost=exc.cost, have=exc.have), show_alert=True)
        return
    view = await get_view(session, redis, callback.from_user.id)
    await callback.answer(LEVEL_UP_ALERT.format(name=PATH_NAMES[view.active2 if slot == 2 else view.active], level=level))
    text, markup = await render_path(session, redis, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_PATH_ACTIVATE_PREFIX))
async def cb_path_activate(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    code = callback.data.removeprefix(CB_PATH_ACTIVATE_PREFIX)
    try:
        await activate(session, redis, callback.from_user.id, code)
    except PathNotOwnedError:
        await callback.answer(NOT_OWNED_ALERT, show_alert=True)
        return
    except SwapOnCooldownError as exc:
        await callback.answer(SWAP_COOLDOWN_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
        return
    await callback.answer(ACTIVATED_ALERT.format(name=PATH_NAMES[code]))
    text, markup = await render_path(session, redis, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_PATH_ACTIVATE2_PREFIX))
async def cb_path_activate2(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    code = callback.data.removeprefix(CB_PATH_ACTIVATE2_PREFIX)
    try:
        await activate2(session, redis, callback.from_user.id, code)
    except NoSecondBodyError:
        await callback.answer(NO_SECOND_BODY_ALERT, show_alert=True)
        return
    except PathNotOwnedError:
        await callback.answer(NOT_OWNED_ALERT, show_alert=True)
        return
    except SwapOnCooldownError as exc:
        await callback.answer(SWAP_COOLDOWN_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
        return
    await callback.answer(ACTIVATED_ALERT.format(name=PATH_NAMES[code]))
    text, markup = await render_path(session, redis, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)
