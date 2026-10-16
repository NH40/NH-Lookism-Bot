"""События на карте — экран босса, бой, пуши о появлении (хендлеры).

Метки событий показывает экран карты (`handlers/map` → `keyboards/event.event_rows`).
`send_spawn_pushes()` — публичная функция домена для фонового прохода (`main.py`).
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.services.position_skill import journal_block
from bot.config.event import BOSS_POWER_PERCENT, EVENT_PUSH_BATCH, EVENT_PUSH_PAUSE_SECONDS
from bot.constant.event import (
    BOSS_FRAGMENT,
    CB_EVENT_FIGHT_PREFIX,
    CB_EVENT_VIEW_PREFIX,
    EVENT_BOSS,
    EVENT_SCHOOL_TEACHER,
    EVENT_TEACHER,
)
from bot.constant.settings import NOTIFY_BOSS, NOTIFY_SCHOOL, NOTIFY_TEACHER
from bot.db.repositories.user import get_by_id
from bot.db.repositories.clan import member_ids as clan_member_ids
from bot.handlers.school import render_school_teacher
from bot.handlers.unique_technique import render_teacher
from bot.keyboards.event import boss_menu
from bot.services.district import (
    BattleOnCooldownError,
    BossAlreadyDefeatedError,
    EventGoneError,
    NoAttackersError,
    fight_boss,
)
from bot.services.event import SpawnedEvent, list_active, push_recipients
from bot.texts.district import BATTLE_COOLDOWN, NO_ATTACKERS
from bot.texts.event import (
    BOSS_ABILITIES,
    BOSS_ALREADY_DEFEATED_ALERT,
    BOSS_LOST,
    BOSS_NAMES,
    BOSS_RESULT,
    BOSS_REWARD,
    BOSS_SCREEN,
    BOSS_SCREEN_DONE,
    BOSS_WON,
    EVENT_GONE_ALERT,
    FRAGMENT_EMOJI,
    FRAGMENT_NAMES,
    PUSH_BOSS_SPAWNED,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.formatting import format_countdown, format_number
from bot.utils.notify import notify
from bot.utils.safe_edit import safe_edit_text
from bot.services.foresight import vs_boss as forecast_vs_boss
from bot.texts.foresight import forecast_line

log = logging.getLogger(__name__)
router = Router(name="event")


def _parse_id(raw: str) -> int | None:
    return int(raw) if raw.isdigit() else None


@router.callback_query(F.data.startswith(CB_EVENT_VIEW_PREFIX))
async def cb_event_view(callback: CallbackQuery, session: AsyncSession) -> None:
    event_id = _parse_id(callback.data.removeprefix(CB_EVENT_VIEW_PREFIX))
    events = {e.id: e for e in await list_active(session, callback.from_user.id)}
    event = events.get(event_id)
    if event is None:
        await callback.answer(EVENT_GONE_ALERT, show_alert=True)
        return
    if event.kind != EVENT_BOSS:
        # Учитель статистов — домен школ, учитель техник — домен уникальных техник.
        await callback.answer()
        render = render_school_teacher if event.kind == EVENT_SCHOOL_TEACHER else render_teacher
        text, markup = await render(session, callback.from_user.id, event.id)
        await safe_edit_text(callback.message, text, reply_markup=markup)
        return
    await callback.answer()
    kind = BOSS_FRAGMENT[event.code]
    text = BOSS_SCREEN.format(
        name=BOSS_NAMES[event.code],
        ability=BOSS_ABILITIES[event.code],
        percent=BOSS_POWER_PERCENT[event.code],
        emoji=FRAGMENT_EMOJI[kind],
        fragment_name=FRAGMENT_NAMES[kind],
        countdown=format_countdown(event.ends_in_seconds),
    )
    if event.won:
        text += BOSS_SCREEN_DONE
    else:
        user = await get_by_id(session, callback.from_user.id)
        text += forecast_line(await forecast_vs_boss(session, user.id, event.code, user.phase))
    await safe_edit_text(callback.message, text, reply_markup=boss_menu(event.id, can_fight=not event.won))


@router.callback_query(F.data.startswith(CB_EVENT_FIGHT_PREFIX))
async def cb_event_fight(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    event_id = _parse_id(callback.data.removeprefix(CB_EVENT_FIGHT_PREFIX))
    user = await get_by_id(session, callback.from_user.id)
    if user is None or user.city_id is None or event_id is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    # Popup-тексты — без HTML.
    try:
        result = await fight_boss(session, redis, user, event_id)
    except EventGoneError:
        await callback.answer(EVENT_GONE_ALERT, show_alert=True)
        return
    except BossAlreadyDefeatedError:
        await callback.answer(BOSS_ALREADY_DEFEATED_ALERT, show_alert=True)
        return
    except NoAttackersError:
        await callback.answer(NO_ATTACKERS, show_alert=True)
        return
    except BattleOnCooldownError as exc:
        await callback.answer(BATTLE_COOLDOWN.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
        return
    await callback.answer()
    name = BOSS_NAMES[result.boss]
    reward = ""
    if result.won:
        reward = BOSS_REWARD.format(
            emoji=FRAGMENT_EMOJI[result.fragment_kind],
            fragments=format_number(result.fragments),
            fragment_name=FRAGMENT_NAMES[result.fragment_kind],
        )
    await callback.message.answer(
        BOSS_RESULT.format(
            headline=(BOSS_WON if result.won else BOSS_LOST).format(name=name),
            rounds=result.rounds,
            power=format_number(result.attacker_power),
            dead=format_number(result.attacker_dead),
            boss_power=format_number(result.boss_power),
            boss_left=format_number(result.boss_remaining_power),
            reward=reward,
        ) + journal_block(result.journal),
        reply_markup=boss_menu(event_id, can_fight=not result.won),
    )


CLAN_EVENT_PREFIX = "🏰 <b>Клановое событие.</b> "

# Категория пуша (выключатель в «🔔 Уведомлениях») для каждого вида события на карте.
_EVENT_CATEGORY: dict[str, str] = {EVENT_BOSS: NOTIFY_BOSS, EVENT_TEACHER: NOTIFY_TEACHER, EVENT_SCHOOL_TEACHER: NOTIFY_SCHOOL}


def spawn_push_text(event: SpawnedEvent) -> str | None:
    if event.kind == EVENT_BOSS:
        kind = BOSS_FRAGMENT[event.code]
        return PUSH_BOSS_SPAWNED.format(
            name=BOSS_NAMES[event.code],
            duration=format_countdown(event.duration_seconds),
            emoji=FRAGMENT_EMOJI[kind],
            fragment_name=FRAGMENT_NAMES[kind],
        )
    return None


async def send_spawn_pushes(
    bot: Bot, session_factory: async_sessionmaker[AsyncSession], events: list[SpawnedEvent], extra_texts=None
) -> None:
    """Пуш о новых событиях заходившим недавно игрокам — пачками с паузой (лимиты Telegram).
    `extra_texts` — тексты событий других доменов (учителя), по событию → текст. Каждый
    получатель видит только события тех категорий, что не выключил в «🔔 Уведомлениях»
    (`users.notify_muted` пришёл тем же запросом, что и список получателей)."""
    items = [
        (_EVENT_CATEGORY[e.kind], t, e.clan_id)
        for e in events
        if (t := spawn_push_text(e) or (extra_texts(e) if extra_texts else None))
    ]
    if not items:
        return
    # Клановые события (Сторожевая башня, Додзё) — только участникам своего клана.
    clan_members: dict[int, set[int]] = {}
    clan_ids = {c for *_, c in items if c is not None}
    if clan_ids:
        async with session_factory() as session:
            for clan_id in clan_ids:
                clan_members[clan_id] = set(await clan_member_ids(session, clan_id))
    sent = 0
    for user_id, muted in await push_recipients(session_factory):
        text = "\n\n".join(
            (CLAN_EVENT_PREFIX if clan_id else "") + t
            for category, t, clan_id in items
            if category not in muted and (clan_id is None or user_id in clan_members.get(clan_id, ()))
        )
        if not text:
            continue
        await notify(bot, user_id, text)
        sent += 1
        if sent % EVENT_PUSH_BATCH == 0:
            await asyncio.sleep(EVENT_PUSH_PAUSE_SECONDS)
