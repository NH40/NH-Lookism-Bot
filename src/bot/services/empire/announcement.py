"""Объявления императора игрокам его земель (пользователь 2026-11-06).

Раз в `KEY_CD_EMPIRE_ANNOUNCE` (по умолчанию 4 часа, меняется в админке) император пишет всем,
кто платит ему налог. Кто выключил категорию `NOTIFY_EMPEROR` в уведомлениях, сообщения не
получает. Император видит «получили X из N»: Telegram не сообщает боту о прочтении, поэтому
«получил» значит, что сообщение принято Telegram; выключившие и заблокировавшие бота не считаются.
Журнал открыт всем жителям города, в том числе выключившим пуши: они смотрят его сами.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.cache.keys import empire_announce_cooldown
from bot.config.empire import (
    EMPIRE_ANNOUNCE_BATCH_PAUSE_SECONDS,
    EMPIRE_ANNOUNCE_BATCH_SIZE,
    EMPIRE_ANNOUNCE_LOG_PAGE_SIZE,
    EMPIRE_ANNOUNCE_MAX_CHARS,
    EMPIRE_ANNOUNCE_SENT_SHOWN,
)
from bot.constant.admin.live_config import KEY_CD_EMPIRE_ANNOUNCE
from bot.constant.settings import NOTIFY_EMPEROR
from bot.db.models.emperor_announcement import EmperorAnnouncement
from bot.db.repositories import empire as empire_repo
from bot.db.repositories.gang import get_by_user as get_gang_row
from bot.db.repositories.phase import get_phase
from bot.db.repositories.user import get_by_id
from bot.services.admin.live_config import cooldown_seconds
from bot.services.phase import is_emperor
from bot.texts.empire import ANNOUNCE_PUSH, ANNOUNCE_REPORT, ANNOUNCE_UNNAMED
from bot.utils.formatting import esc, format_number

log = logging.getLogger(__name__)


class AnnounceNotEmperorError(Exception):
    pass


class AnnounceTextError(Exception):
    """Пустой текст или длиннее предела."""


class AnnounceNoSubjectsError(Exception):
    """На землях императора некому писать — КД не тратится."""


class AnnounceOnCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class AnnounceView:
    cooldown_seconds: int
    subjects: int
    muted: int
    sent: list[EmperorAnnouncement]


@dataclass(frozen=True, slots=True)
class Published:
    announcement_id: int
    emperor_id: int
    emperor_name: str
    text: str
    recipient_ids: list[int]
    recipients: int
    muted: int


@dataclass(frozen=True, slots=True)
class LogPage:
    items: list[EmperorAnnouncement]
    page: int
    has_more: bool


async def _ensure_emperor(session: AsyncSession, user_id: int) -> None:
    current = await get_phase(session, user_id)
    if current is None or not is_emperor(current[0]):
        raise AnnounceNotEmperorError


def clean_text(raw: str | None) -> str:
    text = (raw or "").strip()
    if not text or len(text) > EMPIRE_ANNOUNCE_MAX_CHARS:
        raise AnnounceTextError
    return text


async def get_announce_view(session: AsyncSession, redis: Redis, user_id: int) -> AnnounceView:
    await _ensure_emperor(session, user_id)
    subjects = await empire_repo.list_subjects(session, user_id, NOTIFY_EMPEROR)
    return AnnounceView(
        cooldown_seconds=max(0, await redis.ttl(empire_announce_cooldown(user_id))),
        subjects=len(subjects),
        muted=sum(1 for _, muted in subjects if muted),
        sent=await empire_repo.list_sent(session, user_id, EMPIRE_ANNOUNCE_SENT_SHOWN),
    )


async def _emperor_name(session: AsyncSession, user_id: int) -> str:
    user = await get_by_id(session, user_id)
    gang = await get_gang_row(session, user_id)
    if user is not None and user.display_name:
        return user.display_name
    if gang is not None:
        return gang.name
    return f"@{user.username}" if user is not None and user.username else ANNOUNCE_UNNAMED


async def publish(session: AsyncSession, redis: Redis, user_id: int, raw_text: str | None) -> Published:
    """Записать объявление и занять КД. `SET NX` — одна отправка на КД, он же защита от двойного
    клика; при сбое КД снимается. Коммитит. Саму рассылку запускает вызывающий через `deliver`."""
    await _ensure_emperor(session, user_id)
    text = clean_text(raw_text)
    key = empire_announce_cooldown(user_id)
    ttl = await redis.ttl(key)
    if ttl > 0:
        raise AnnounceOnCooldownError(ttl)
    subjects = await empire_repo.list_subjects(session, user_id, NOTIFY_EMPEROR)
    if not subjects:
        raise AnnounceNoSubjectsError
    # КД 0 в админке выключает перерыв, но Redis не принимает EX 0: ключ живёт секунду ради двойного клика.
    if not await redis.set(key, "1", nx=True, ex=max(1, cooldown_seconds(KEY_CD_EMPIRE_ANNOUNCE))):
        raise AnnounceOnCooldownError(max(0, await redis.ttl(key)))
    try:
        name = await _emperor_name(session, user_id)
        muted = sum(1 for _, is_muted in subjects if is_muted)
        row = await empire_repo.create_announcement(
            session, emperor_id=user_id, emperor_name=name, text=text,
            city_ids=await empire_repo.emperor_city_ids(session, user_id),
            recipients=len(subjects), muted=muted,
        )
        announcement_id = row.id
        await session.commit()
    except Exception:
        await session.rollback()
        await redis.delete(key)
        raise
    return Published(
        announcement_id=announcement_id, emperor_id=user_id, emperor_name=name, text=text,
        recipient_ids=[uid for uid, is_muted in subjects if not is_muted], recipients=len(subjects), muted=muted,
    )


async def _send(bot: Bot, user_id: int, text: str) -> bool:
    for _ in range(2):
        try:
            await bot.send_message(user_id, text)
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except Exception:  # noqa: BLE001 — заблокировал бота, удалён и т.п.
            return False
    return False


async def deliver(bot: Bot, session_factory: async_sessionmaker[AsyncSession], published: Published) -> None:
    """Фоновая рассылка своей сессией: хендлер к этому моменту уже завершён. Счётчик пишется
    партиями, поэтому император видит рост, а после сбоя остаётся честное число."""
    text = ANNOUNCE_PUSH.format(name=esc(published.emperor_name), text=esc(published.text))
    delivered = 0
    pending = 0
    try:
        for i, user_id in enumerate(published.recipient_ids, 1):
            if await _send(bot, user_id, text):
                delivered += 1
                pending += 1
            if i % EMPIRE_ANNOUNCE_BATCH_SIZE == 0:
                if pending:
                    await _flush(session_factory, published.announcement_id, pending)
                    pending = 0
                await asyncio.sleep(EMPIRE_ANNOUNCE_BATCH_PAUSE_SECONDS)
        if pending:
            await _flush(session_factory, published.announcement_id, pending)
        await _send(
            bot, published.emperor_id,
            ANNOUNCE_REPORT.format(
                delivered=format_number(delivered), recipients=format_number(published.recipients),
                muted=format_number(published.muted),
                failed=format_number(len(published.recipient_ids) - delivered),
            ),
        )
    except Exception:
        log.exception("Emperor announcement %s delivery failed", published.announcement_id)


async def _flush(session_factory: async_sessionmaker[AsyncSession], announcement_id: int, count: int) -> None:
    async with session_factory() as session:
        await empire_repo.add_delivered(session, announcement_id, count)
        await session.commit()


async def get_log(session: AsyncSession, user_id: int, page: int) -> LogPage:
    """Журнал игрока: объявления, рассылавшиеся на его город, новые сверху."""
    user = await get_by_id(session, user_id)
    if user is None or user.city_id is None:
        return LogPage(items=[], page=0, has_more=False)
    page = max(page, 0)
    rows = await empire_repo.list_for_city(
        session, user.city_id, page * EMPIRE_ANNOUNCE_LOG_PAGE_SIZE, EMPIRE_ANNOUNCE_LOG_PAGE_SIZE + 1
    )
    return LogPage(items=rows[:EMPIRE_ANNOUNCE_LOG_PAGE_SIZE], page=page, has_more=len(rows) > EMPIRE_ANNOUNCE_LOG_PAGE_SIZE)
