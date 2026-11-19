"""Объявления клана (пользователь 2026-11-19): владелец или зам пишет, участникам приходит пуш
(категория «Клан» — выключается в уведомлениях), последнее объявление висит на экране клана.

Одно объявление на клан в `CLAN_ANNOUNCE_COOLDOWN_SECONDS` (`SET NX` в Redis — он же защита от
двойного клика; при сбое записи КД снимается). Рассылка — фоном своей сессией, с паузой между
пушами: лимит Telegram общий с ботом.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.clan import CLAN_ANNOUNCE_COOLDOWN_SECONDS, CLAN_ANNOUNCE_MAX, CLAN_ANNOUNCE_SEND_GAP_SECONDS
from bot.constant.clan import MANAGER_RANKS
from bot.constant.settings import NOTIFY_CLAN
from bot.db.models.clan import Clan
from bot.db.repositories import clan as clan_repo
from bot.services.clan.clan import ClanError, require_member

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ClanAnnouncement:
    clan_name: str
    author: str
    text: str
    recipient_ids: list[int]


def _key(clan_id: int) -> str:
    return f"clan:announce:{clan_id}"


def clean_text(raw: str | None) -> str:
    text = (raw or "").strip()
    if not text or len(text) > CLAN_ANNOUNCE_MAX:
        raise ClanError("announce_text", CLAN_ANNOUNCE_MAX)
    return text


async def cooldown_left(redis: Redis, clan_id: int) -> int:
    return max(0, await redis.ttl(_key(clan_id)))


async def publish(session: AsyncSession, redis: Redis, user_id: int, raw_text: str | None) -> ClanAnnouncement:
    """Записать объявление на экран клана и занять КД. Коммитит. Рассылку запускает вызывающий (`deliver`)."""
    member = await require_member(session, user_id, MANAGER_RANKS)
    text = clean_text(raw_text)
    key = _key(member.clan_id)
    if not await redis.set(key, "1", nx=True, ex=CLAN_ANNOUNCE_COOLDOWN_SECONDS):
        raise ClanError("announce_cooldown", max(1, await redis.ttl(key) // 60))
    try:
        clan = await clan_repo.get(session, member.clan_id)
        author = (await clan_repo.member_labels(session, [user_id]))[user_id][0]
        await session.execute(
            update(Clan).where(Clan.id == member.clan_id).values(announcement=text, announcement_at=datetime.now(timezone.utc))
        )
        await clan_repo.log(session, member.clan_id, f"📣 {author}: объявление")
        ids = [uid for uid in await clan_repo.member_ids(session, member.clan_id) if uid != user_id]
        name = clan.name
        await session.commit()
    except Exception:
        await session.rollback()
        await redis.delete(key)
        raise
    return ClanAnnouncement(clan_name=name, author=author, text=text, recipient_ids=ids)


async def deliver(bot: Bot, session_factory: async_sessionmaker[AsyncSession], ann: ClanAnnouncement) -> int:
    """Фоновая рассылка: каждому участнику, кто не выключил пуши клана. → сколько отправлено."""
    from bot.services.settings import notify_player
    from bot.texts.clan import ANNOUNCE_PUSH
    from bot.utils.formatting import esc

    text = ANNOUNCE_PUSH.format(clan=esc(ann.clan_name), author=esc(ann.author), text=esc(ann.text))
    sent = 0
    try:
        async with session_factory() as session:
            for uid in ann.recipient_ids:
                if await notify_player(bot, session, uid, NOTIFY_CLAN, text):
                    sent += 1
                await asyncio.sleep(CLAN_ANNOUNCE_SEND_GAP_SECONDS)
    except Exception:
        log.exception("Clan announcement delivery failed (%s)", ann.clan_name)
    return sent
