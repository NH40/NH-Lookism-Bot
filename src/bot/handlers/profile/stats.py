"""Профиль — экран характеристик: ранги, очки развития, вложение очков (хендлеры).

raw-notes «Профиль»/«Тренировки»: «получив на тренировке очки характеристики, игрок в
профиле поднимает себе свои характеристики». Логика — `services/characteristic`.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.characteristic import CB_STATS_OPEN, CB_STATS_UP_PREFIX
from bot.keyboards.profile import stats_menu
from bot.services.characteristic import (
    NotEnoughPointsError,
    StatMaxedError,
    StatsView,
    UnknownStatError,
    get_stats_view,
    invest,
)
from bot.services.gang import get_gang
from bot.services.mastery import check_unlock
from bot.handlers.unique_path import notify_conviction
from bot.texts.profile import (
    NOT_ONBOARDED,
    POTENTIAL_LABELS,
    POTENTIAL_LINE,
    STAT_EFFECT_LINE,
    STAT_EFFECTS,
    STAT_INVESTED,
    STAT_LABELS,
    STAT_MAXED,
    STAT_NOT_ENOUGH,
    STAT_SCREEN_LINE,
    STAT_SCREEN_LINE_MAX,
    STATS_SCREEN,
)
from bot.utils.formatting import format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="profile_stats")


def render_stats_screen(view: StatsView):
    lines = []
    for stat in view.stats:
        if stat.next_cost is None:
            lines.append(STAT_SCREEN_LINE_MAX.format(label=STAT_LABELS[stat.code], rank=stat.rank))
        else:
            lines.append(STAT_SCREEN_LINE.format(label=STAT_LABELS[stat.code], rank=stat.rank, cost=stat.next_cost))
    lines.append(POTENTIAL_LINE.format(potential=POTENTIAL_LABELS[view.potential]))
    effects = "\n".join(
        STAT_EFFECT_LINE.format(label=STAT_LABELS[s.code], effect=STAT_EFFECTS[s.code]) for s in view.stats
    )
    text = STATS_SCREEN.format(lines="\n".join(lines), effects=effects, points=format_number(view.dev_points))
    return text, stats_menu([(s.code, s.next_cost is not None) for s in view.stats])


@router.callback_query(F.data == CB_STATS_OPEN)
async def cb_stats_open(callback: CallbackQuery, session: AsyncSession) -> None:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    text, markup = render_stats_screen(await get_stats_view(session, callback.from_user.id))
    await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_STATS_UP_PREFIX))
async def cb_stats_up(callback: CallbackQuery, session: AsyncSession) -> None:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        stat, mode = callback.data.removeprefix(CB_STATS_UP_PREFIX).split(":")
        result = await invest(session, callback.from_user.id, stat, mode)
    except (ValueError, UnknownStatError):
        await callback.answer()
        return
    except StatMaxedError:
        await callback.answer(STAT_MAXED, show_alert=True)
        return
    except NotEnoughPointsError as exc:
        # Popup — без HTML.
        await callback.answer(STAT_NOT_ENOUGH.format(cost=exc.cost, points=format_number(exc.points)), show_alert=True)
        return
    await callback.answer(
        STAT_INVESTED.format(label=STAT_LABELS[result.stat], ranks=result.ranks, rank=result.new_rank, cost=result.cost)
    )
    # Все четыре характеристики дошли до EXR — назначаем задание «Преодоление стены».
    await check_unlock(session, callback.from_user.id)
    await notify_conviction(callback.message, session, callback.from_user.id)
    text, markup = render_stats_screen(await get_stats_view(session, callback.from_user.id))
    await safe_edit_text(callback.message, text, reply_markup=markup)
