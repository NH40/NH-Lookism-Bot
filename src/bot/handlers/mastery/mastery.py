"""Мастерство — экран цепочки «Преодоление стены», бой с Томом Ли, вложение очков (хендлеры).

Вход — «🥋 Мастерство» в меню профиля и кнопка под пушем о новом задании.
`send_quest_pushes()` — публичная функция домена: фоновый проход (`main.py`) уведомляет
игроков, у которых наступил этап.
"""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.position_skill import journal_block
from bot.constant.characteristic import MASTERIES
from bot.constant.mastery import (
    CB_MASTERY_INVEST_PREFIX,
    CB_MASTERY_OPEN,
    CB_MASTERY_TOM_FIGHT,
    QUEST_ACTIVE,
    QUEST_COMPLETE,
    QUEST_PENDING,
    QUEST_TRAINER,
    TASK_TOM,
)
from bot.db.repositories.user import get_by_id
from bot.keyboards.mastery import mastery_menu, open_mastery_menu
from bot.services.district import BattleOnCooldownError, NoAttackersError, fight_tom
from bot.services.gang import get_gang
from bot.services.mastery import (
    MasteryCappedError,
    MasteryView,
    NoFreePointsError,
    QuestNotActiveError,
    TomLockedError,
    get_view,
    invest_point,
)
from bot.texts.district import BATTLE_COOLDOWN, NO_ATTACKERS
from bot.texts.mastery import (
    CHAIN_COMPLETE_ALERT,
    FREE_POINTS_LINE,
    INVESTED_ALERT,
    MASTERY_CAPPED_ALERT,
    MASTERY_SCREEN,
    NO_FREE_POINTS_ALERT,
    PUSH_QUEST,
    QUEST_ACTIVE as QUEST_ACTIVE_TEXT,
    QUEST_COMPLETE as QUEST_COMPLETE_TEXT,
    QUEST_LOCKED,
    QUEST_NOT_ACTIVE_ALERT,
    QUEST_PENDING as QUEST_PENDING_TEXT,
    QUEST_TRAINER as QUEST_TRAINER_TEXT,
    STAGE_FINISHED_ALERT,
    STAGE_NAMES,
    TASK_DONE,
    TASK_LABELS,
    TASK_LOCKED,
    TASK_PROGRESS,
    TASK_TODO,
    TIER_LINE,
    TOM_HINT,
    TOM_LOCKED_ALERT,
    TOM_LOST,
    TOM_RESULT,
    TOM_WON,
)
from bot.texts.profile import MASTERY_LABELS, MASTERY_TIER_LABELS, NOT_ONBOARDED
from bot.utils.formatting import format_countdown, format_number
from bot.services.settings import notify_player
from bot.constant.settings import NOTIFY_MASTERY
from bot.utils.safe_edit import safe_edit_text

router = Router(name="mastery")


def _quest_block(view: MasteryView) -> str:
    if view.status is None:
        return QUEST_LOCKED
    stage_name = STAGE_NAMES.get(view.stage, "")
    if view.status == QUEST_PENDING:
        return QUEST_PENDING_TEXT.format(
            stage=view.stage, stage_name=stage_name, countdown=format_countdown(view.available_in_seconds or 0)
        )
    if view.status == QUEST_COMPLETE:
        return QUEST_COMPLETE_TEXT
    if view.status == QUEST_TRAINER:
        text = QUEST_TRAINER_TEXT.format(
            price=format_number(view.price or 0), bought=view.points_bought, free=view.points_free, stage_name=stage_name
        )
        return text
    lines = []
    for task in view.tasks:
        label = TASK_LABELS[task.code]
        if task.locked:
            lines.append(TASK_LOCKED.format(label=label))
        elif task.done:
            lines.append(TASK_DONE.format(label=label))
        elif task.target > 1:
            lines.append(TASK_PROGRESS.format(label=label, progress=task.progress, target=task.target))
        else:
            lines.append(TASK_TODO.format(label=label))
    text = QUEST_ACTIVE_TEXT.format(stage=view.stage, stage_name=stage_name, tasks="\n".join(lines))
    if view.tom_unlocked or any(t.code == TASK_TOM for t in view.tasks):
        text += TOM_HINT.format(power=format_number(view.tom_power))
    return text


def render_mastery(view: MasteryView):
    tiers = "\n".join(
        TIER_LINE.format(
            label=MASTERY_LABELS[m],
            tier=MASTERY_TIER_LABELS[view.mastery[m]],
        )
        for m in MASTERIES
    )
    quest = _quest_block(view)
    if view.points_free:
        quest += FREE_POINTS_LINE.format(free=view.points_free)
    investable = [m for m in MASTERIES if view.mastery[m] < view.stage] if view.points_free else []
    markup = mastery_menu(
        tom=view.status == QUEST_ACTIVE and view.tom_unlocked,
        investable=investable,
        shop=view.status == QUEST_TRAINER,
    )
    return MASTERY_SCREEN.format(tiers=tiers, quest_block=quest), markup


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


@router.callback_query(F.data == CB_MASTERY_OPEN)
async def cb_mastery_open(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    text, markup = render_mastery(await get_view(session, callback.from_user.id))
    await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data == CB_MASTERY_TOM_FIGHT)
async def cb_mastery_tom(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user = await get_by_id(session, callback.from_user.id)
    if user is None or user.city_id is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    # Popup-тексты — без HTML.
    try:
        result = await fight_tom(session, redis, user)
    except QuestNotActiveError:
        await callback.answer(QUEST_NOT_ACTIVE_ALERT, show_alert=True)
        return
    except TomLockedError:
        await callback.answer(TOM_LOCKED_ALERT, show_alert=True)
        return
    except NoAttackersError:
        await callback.answer(NO_ATTACKERS, show_alert=True)
        return
    except BattleOnCooldownError as exc:
        await callback.answer(BATTLE_COOLDOWN.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        TOM_RESULT.format(
            headline=TOM_WON if result.won else TOM_LOST,
            rounds=result.rounds,
            power=format_number(result.attacker_power),
            dead=format_number(result.attacker_dead),
            tom_power=format_number(result.tom_power),
            tom_left=format_number(result.tom_remaining_power),
        ) + journal_block(result.journal),
        reply_markup=open_mastery_menu(),
    )


@router.callback_query(F.data.startswith(CB_MASTERY_INVEST_PREFIX))
async def cb_mastery_invest(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    mastery = callback.data.removeprefix(CB_MASTERY_INVEST_PREFIX)
    try:
        result = await invest_point(session, callback.from_user.id, mastery)
    except NoFreePointsError:
        await callback.answer(NO_FREE_POINTS_ALERT, show_alert=True)
        return
    except MasteryCappedError:
        await callback.answer(MASTERY_CAPPED_ALERT, show_alert=True)
        return
    label, tier = MASTERY_LABELS[result.mastery], MASTERY_TIER_LABELS[result.new_tier]
    if result.chain_complete:
        await callback.answer(CHAIN_COMPLETE_ALERT.format(label=label, tier=tier), show_alert=True)
    elif result.stage_finished:
        await callback.answer(STAGE_FINISHED_ALERT.format(label=label, tier=tier), show_alert=True)
    else:
        await callback.answer(INVESTED_ALERT.format(label=label, tier=tier))
    text, markup = render_mastery(await get_view(session, callback.from_user.id))
    await safe_edit_text(callback.message, text, reply_markup=markup)


async def send_quest_pushes(bot: Bot, session: AsyncSession, activated: list[tuple[int, int]]) -> None:
    """Пуш о наступившем этапе цепочки (best-effort — игрок мог заблокировать бота)."""
    for user_id, stage in activated:
        await notify_player(
            bot, session, user_id, NOTIFY_MASTERY, PUSH_QUEST.format(stage=stage, stage_name=STAGE_NAMES.get(stage, "")),
            reply_markup=open_mastery_menu(),
        )
