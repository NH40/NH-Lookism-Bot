"""Админка: аудитории, массовая выдача (один SQL), рассылка фоновой задачей батчами."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import Integer, case, cast, exists, func, literal_column, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select

from bot.config.game import TICKET_CAP, TICKET_REGEN_SECONDS
from bot.constant.admin.mass import (
    ACTIVE_7D_HOURS,
    ACTIVE_24H_HOURS,
    BROADCAST_BATCH_PAUSE_SECONDS,
    BROADCAST_BATCH_SIZE,
    FILTERS,
    FLT_ACTIVE_7D,
    FLT_ACTIVE_24H,
    FLT_CLAN,
    FLT_DONORS,
    FLT_NO_ROLE,
)
from bot.constant.resource import RES_TICKETS, RESOURCES
from bot.db.models.clan import Clan, ClanMember
from bot.db.models.donate import Payment
from bot.db.models.user import User
from bot.services.admin import audit
from bot.services.resource.resource import _COLUMNS

log = logging.getLogger(__name__)


class MassError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Audience:
    code: str
    clan_id: int | None = None


def audience_stmt(aud: Audience) -> Select:
    """`SELECT id` по аудитории. Таблица users — под алиасом, иначе во вложенном запросе
    UPDATE ... IN (SELECT ...) SQLAlchemy авто-коррелировал бы её и выбросил из FROM."""
    if aud.code not in FILTERS:
        raise MassError(aud.code)
    u = aliased(User)
    stmt = select(u.id)
    now = datetime.now(timezone.utc)
    if aud.code == FLT_ACTIVE_24H:
        stmt = stmt.where(u.last_active_at >= now - timedelta(hours=ACTIVE_24H_HOURS))
    elif aud.code == FLT_ACTIVE_7D:
        stmt = stmt.where(u.last_active_at >= now - timedelta(hours=ACTIVE_7D_HOURS))
    elif aud.code == FLT_DONORS:
        stmt = stmt.where(or_(u.donate_coins > 0, exists().where(Payment.user_id == u.id, Payment.amount_rub > 0)))
    elif aud.code == FLT_CLAN:
        stmt = stmt.where(u.id.in_(select(ClanMember.user_id).where(ClanMember.clan_id == aud.clan_id)))
    elif aud.code == FLT_NO_ROLE:
        stmt = stmt.where(u.admin_role.is_(None))
    return stmt


async def count_audience(session: AsyncSession, aud: Audience) -> int:
    return int(await session.scalar(select(func.count()).select_from(audience_stmt(aud).subquery())) or 0)


async def find_clan(session: AsyncSession, query: str) -> Clan | None:
    query = query.strip()
    if query.isdigit():
        clan = await session.get(Clan, int(query))
        if clan is not None:
            return clan
    return await session.scalar(select(Clan).where(func.lower(Clan.name) == query.lower()))


def audience_details(aud: Audience) -> dict:
    return {"filter": aud.code, "clan_id": aud.clan_id}


# ----------------------------------------------------------------- выдача

def ticket_grant_values(amount: int) -> dict:
    """Тикеты: реген фиксируется в том же UPDATE (те же правила, что `db/repositories/ticket`:
    выше капа таймер стоит), затем +amount. Кап — базовый (без бонусов систем развития)."""
    cap, interval = TICKET_CAP, TICKET_REGEN_SECONDS
    ticks = cast(func.floor(func.extract("epoch", func.now() - User.tickets_updated_at) / interval), Integer)
    regen_count = case((User.tickets_count >= cap, User.tickets_count), else_=func.least(cap, User.tickets_count + ticks))
    regen_at = case(
        (or_(User.tickets_count >= cap, User.tickets_count + ticks >= cap), func.now()),
        else_=User.tickets_updated_at + (ticks * interval) * literal_column("interval '1 second'"),
    )
    return {User.tickets_count: regen_count + amount, User.tickets_updated_at: regen_at}


async def mass_grant(session: AsyncSession, admin_id: int, aud: Audience, resource: str, amount: int) -> int:
    """Начислить `amount` ресурса всей аудитории одним UPDATE + одна запись аудита. → число
    затронутых игроков. Коммитит."""
    if resource not in RESOURCES or amount <= 0:
        raise MassError(resource)
    values = ticket_grant_values(amount) if resource == RES_TICKETS else {_COLUMNS[resource]: _COLUMNS[resource] + amount}
    result = await session.execute(
        update(User).where(User.id.in_(audience_stmt(aud))).values(values).execution_options(synchronize_session=False)
    )
    affected = result.rowcount
    await audit.log(
        session, admin_id, "mass_grant", None,
        {**audience_details(aud), "resource": resource, "amount": amount, "affected": affected},
    )
    await session.commit()
    return affected


# --------------------------------------------------------------- рассылка

@dataclass(frozen=True, slots=True)
class Content:
    text: str  # HTML
    photo: str | None = None  # file_id
    btn_text: str | None = None
    btn_url: str | None = None

    def to_dict(self) -> dict:
        return {"text": self.text, "photo": self.photo, "btn_text": self.btn_text, "btn_url": self.btn_url}

    @staticmethod
    def from_dict(data: dict) -> "Content":
        return Content(data["text"], data.get("photo"), data.get("btn_text"), data.get("btn_url"))


def parse_button(raw: str) -> tuple[str, str] | None:
    """«текст | https://...» → (текст, url) либо None."""
    text, sep, url = raw.partition("|")
    text, url = text.strip(), url.strip()
    if not sep or not text or len(text) > 64 or not url.startswith(("https://", "http://", "tg://")):
        return None
    return text, url


def _markup(content: Content) -> InlineKeyboardMarkup | None:
    if not content.btn_text or not content.btn_url:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=content.btn_text, url=content.btn_url)]])


async def send_content(bot: Bot, chat_id: int, content: Content) -> None:
    markup = _markup(content)
    if content.photo:
        await bot.send_photo(chat_id, content.photo, caption=content.text or None, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await bot.send_message(chat_id, content.text, parse_mode=ParseMode.HTML, reply_markup=markup)


async def _send_safe(bot: Bot, chat_id: int, content: Content) -> bool:
    for attempt in (1, 2):
        try:
            await send_content(bot, chat_id, content)
            return True
        except TelegramRetryAfter as exc:
            if attempt == 2:
                return False
            await asyncio.sleep(exc.retry_after + 1)
        except TelegramAPIError:
            return False
    return False


async def run_broadcast(
    bot: Bot, session_factory: async_sessionmaker[AsyncSession], aud: Audience, content: Content
) -> tuple[int, int]:
    """Рассылка батчами по `BROADCAST_BATCH_SIZE` с паузой, keyset-пагинация по id. → (отправлено, ошибок)."""
    sent = failed = 0
    last_id = 0
    sub = audience_stmt(aud).subquery()
    while True:
        async with session_factory() as session:
            ids = list(await session.scalars(select(sub.c.id).where(sub.c.id > last_id).order_by(sub.c.id).limit(BROADCAST_BATCH_SIZE)))
        if not ids:
            break
        last_id = ids[-1]
        for uid in ids:
            if await _send_safe(bot, uid, content):
                sent += 1
            else:
                failed += 1
        await asyncio.sleep(BROADCAST_BATCH_PAUSE_SECONDS)
    return sent, failed
