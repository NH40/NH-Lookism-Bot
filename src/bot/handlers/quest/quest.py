"""Ежедневные задания (хендлеры). Вход — «📋 Задания» в главном меню."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import get_settings
from bot.constant.quest import CB_QUEST_ADMIN_COMPLETE
from bot.services.admin.admin import is_admin
from bot.texts.quest import ADMIN_COMPLETED_ALERT
from bot.config.quest import QUEST_SWAPS_PER_DAY, QUESTS_PER_DAY
from bot.constant.common import CB_MENU_QUESTS
from bot.constant.dev_quest import QUEST_CONVICTION, QUEST_SCHOOL, QUEST_TEACHER
from bot.constant.quest import CB_QUEST_REROLL_ALL, CB_QUEST_SCROLL, CB_QUEST_SCROLL_PREFIX, CB_QUEST_SWAP_MENU, CB_QUEST_SWAP_PREFIX
from bot.keyboards.quest import quests_menu, scroll_menu, swap_menu
from bot.services.battle_pass import scroll_count
from bot.services.dev_quest import NoScrollError, QuestNotSkippableError, skip_with_scroll, skippable
from bot.services.gang import get_gang
from bot.services.quest import (
    QuestAlreadyDoneError,
    QuestBusyError,
    QuestNotFoundError,
    QuestStatus,
    RerollUsedError,
    get_status,
    reroll_all,
    swap,
)
from bot.texts.dev_quest import TASK_LABELS
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.quest import (
    ALL_DONE,
    BTN_SWAP_SLOT,
    BUSY_ALERT,
    NEXT_MULT,
    NO_SCROLL_ALERT,
    QUESTS_FOOTER,
    QUESTS_HEADER,
    QUEST_DONE_ALERT,
    QUEST_GONE_ALERT,
    QUEST_ROW,
    REROLLED_ALERT,
    REROLL_FULL_OR_SWAP,
    REROLL_NONE,
    REROLL_SWAPS_LEFT,
    REROLL_USED_ALERT,
    SCROLL_GONE_ALERT,
    SCROLL_NONE,
    SCROLL_PICK,
    SCROLL_QUEST_CONVICTION,
    SCROLL_QUEST_SCHOOL,
    SCROLL_QUEST_TEACHER,
    SCROLL_USED_ALERT,
    SEPARATOR,
    STATUS_DONE,
    STATUS_TODO,
    SWAP_PICK,
    TASK_EMOJI,
    TIER_EMOJI,
)
from bot.texts.school import SCHOOL_NAMES
from bot.texts.unique_technique import TEACHER_NAMES
from bot.utils.formatting import emoji_bar, format_duration, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="quest")


def _label(task: str) -> str:
    return TASK_LABELS.get(task, task)


async def render_quests(session: AsyncSession, user_id: int, status: QuestStatus | None = None):
    status = status or await get_status(session, user_id)
    rows = []
    for q in status.quests:
        percent = int(q.progress * 100 / q.target) if q.target else 100
        rows.append(QUEST_ROW.format(
            status=STATUS_DONE if q.done else STATUS_TODO, emoji=TASK_EMOJI.get(q.task, "📌"), label=_label(q.task),
            tier_emoji=TIER_EMOJI[q.tier], bar=emoji_bar(percent), percent=percent,
            progress=format_number(q.progress), target=format_number(q.target), xp=q.xp,
        ))
    if status.full_reroll_available:
        reroll = REROLL_FULL_OR_SWAP.format(swaps=QUEST_SWAPS_PER_DAY)
    elif status.swaps_left:
        reroll = REROLL_SWAPS_LEFT.format(swaps=status.swaps_left)
    else:
        reroll = REROLL_NONE
    all_done = status.completed >= QUESTS_PER_DAY
    header = QUESTS_HEADER.format(
        reset=format_duration(status.resets_in), completed=status.completed, total=QUESTS_PER_DAY,
        mult=ALL_DONE if all_done else (NEXT_MULT.format(mult=status.next_multiplier) if status.next_multiplier > 1 else ""),
        reroll=reroll,
    )
    footer = QUESTS_FOOTER.format(scrolls=await scroll_count(session, user_id))
    text = f"{header}\n{SEPARATOR}\n" + "\n\n".join(rows) + f"\n{SEPARATOR}\n{footer}"
    has_open = not all_done
    admin = await is_admin(session, user_id, get_settings())
    return text, quests_menu(
        reroll_all=status.full_reroll_available and has_open, swap=status.swaps_left > 0 and has_open, admin=admin
    )


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


async def _show(callback: CallbackQuery, session: AsyncSession, status: QuestStatus | None = None) -> None:
    text, markup = await render_quests(session, callback.from_user.id, status)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_MENU_QUESTS)
async def cb_quests(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    await _show(callback, session)


@router.callback_query(F.data == CB_QUEST_REROLL_ALL)
async def cb_reroll_all(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    try:
        status = await reroll_all(session, redis, callback.from_user.id)
    except QuestBusyError:
        await callback.answer(BUSY_ALERT)
        return
    except RerollUsedError:
        await callback.answer(REROLL_USED_ALERT, show_alert=True)
        await _show(callback, session)
        return
    await callback.answer(REROLLED_ALERT)
    await _show(callback, session, status)


@router.callback_query(F.data == CB_QUEST_SWAP_MENU)
async def cb_swap_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    status = await get_status(session, callback.from_user.id)
    if not status.swaps_left:
        await callback.answer(REROLL_USED_ALERT, show_alert=True)
        await _show(callback, session, status)
        return
    await callback.answer()
    options = [
        (q.slot, BTN_SWAP_SLOT.format(
            emoji=TASK_EMOJI.get(q.task, "📌"), label=_label(q.task),
            progress=format_number(q.progress), target=format_number(q.target),
        ))
        for q in status.quests if not q.done
    ]
    await safe_edit_text(callback.message, SWAP_PICK, reply_markup=swap_menu(options))


@router.callback_query(F.data.startswith(CB_QUEST_SWAP_PREFIX))
async def cb_swap(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    raw = callback.data.removeprefix(CB_QUEST_SWAP_PREFIX)
    if not raw.isdigit() or not await _guard(callback, session):
        await callback.answer()
        return
    try:
        status = await swap(session, redis, callback.from_user.id, int(raw))
    except QuestBusyError:
        await callback.answer(BUSY_ALERT)
        return
    except (RerollUsedError, QuestAlreadyDoneError, QuestNotFoundError) as exc:
        alert = {RerollUsedError: REROLL_USED_ALERT, QuestAlreadyDoneError: QUEST_DONE_ALERT}.get(type(exc), QUEST_GONE_ALERT)
        await callback.answer(alert, show_alert=True)
        await _show(callback, session)
        return
    await callback.answer(REROLLED_ALERT)
    await _show(callback, session, status)


def _dev_quest_label(kind: str, ref: str) -> str:
    if kind == QUEST_TEACHER:
        return SCROLL_QUEST_TEACHER.format(name=TEACHER_NAMES.get(ref, ref))
    if kind == QUEST_SCHOOL:
        return SCROLL_QUEST_SCHOOL.format(name=SCHOOL_NAMES.get(ref, ref))
    return SCROLL_QUEST_CONVICTION if kind == QUEST_CONVICTION else kind


async def _show_scrolls(callback: CallbackQuery, session: AsyncSession) -> None:
    user_id = callback.from_user.id
    options = [(q.id, _dev_quest_label(q.kind, q.ref)) for q in await skippable(session, user_id)]
    text = SCROLL_PICK.format(scrolls=await scroll_count(session, user_id)) + ("" if options else "\n\n" + SCROLL_NONE)
    await safe_edit_text(callback.message, text, reply_markup=scroll_menu(options))


@router.callback_query(F.data == CB_QUEST_SCROLL)
async def cb_scroll_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    await _show_scrolls(callback, session)


@router.callback_query(F.data.startswith(CB_QUEST_SCROLL_PREFIX))
async def cb_scroll_use(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_QUEST_SCROLL_PREFIX)
    if not raw.isdigit() or not await _guard(callback, session):
        await callback.answer()
        return
    # Двойной клик безопасен без лока: квест под FOR UPDATE, второй вызов найдёт его выполненным.
    try:
        await skip_with_scroll(session, callback.from_user.id, int(raw))
    except NoScrollError:
        await callback.answer(NO_SCROLL_ALERT, show_alert=True)
        return
    except QuestNotSkippableError:
        await callback.answer(SCROLL_GONE_ALERT, show_alert=True)
        await _show_scrolls(callback, session)
        return
    await callback.answer(SCROLL_USED_ALERT, show_alert=True)
    await _show_scrolls(callback, session)


@router.callback_query(F.data == CB_QUEST_ADMIN_COMPLETE)
async def cb_quest_admin_complete(callback: CallbackQuery, session: AsyncSession) -> None:
    """Тестовая кнопка админа: выполнить все свои задания (права перепроверяет сервис)."""
    from bot.services.admin.testing import NotAdminError, complete_all_quests

    try:
        daily, dev = await complete_all_quests(session, callback.from_user.id)
    except NotAdminError:
        await callback.answer()
        return
    await callback.answer(ADMIN_COMPLETED_ALERT.format(daily=daily, dev=dev), show_alert=True)
    text, markup = await render_quests(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)
