"""Тикеты в поддержку (сервис, пользователь 2026-11-20).

У игрока одно незакрытое обращение: новое сообщение дописывается в него. Ответ сотрудника (саппорт, модератор,
админ) переводит обращение в «отвечено» и уходит игроку пушем (это делает вызывающий — у него есть бот).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.support import SupportMessage, SupportTicket

OPEN, ANSWERED, CLOSED = "open", "answered", "closed"
MAX_TEXT = 1500
PAGE = 10


class SupportError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Thread:
    ticket: SupportTicket
    messages: list[SupportMessage]


def _clean(text: str | None) -> str:
    t = (text or "").strip()
    if not t or len(t) > MAX_TEXT:
        raise SupportError("text")
    return t


async def open_of(session: AsyncSession, user_id: int) -> SupportTicket | None:
    return await session.scalar(select(SupportTicket).where(SupportTicket.user_id == user_id, SupportTicket.status != CLOSED)
                                .order_by(SupportTicket.id.desc()).limit(1))


async def write(session: AsyncSession, user_id: int, text: str | None) -> SupportTicket:
    """Сообщение игрока: в открытое обращение или новое. Коммитит."""
    t = _clean(text)
    ticket = await open_of(session, user_id)
    if ticket is None:
        ticket = SupportTicket(user_id=user_id, status=OPEN)
        session.add(ticket)
        await session.flush()
    ticket.status, ticket.updated_at = OPEN, datetime.now(timezone.utc)
    session.add(SupportMessage(ticket_id=ticket.id, author_id=user_id, staff=False, text=t))
    await session.commit()
    return ticket


async def thread(session: AsyncSession, ticket_id: int) -> Thread | None:
    ticket = await session.get(SupportTicket, ticket_id)
    if ticket is None:
        return None
    msgs = list(await session.scalars(select(SupportMessage).where(SupportMessage.ticket_id == ticket_id).order_by(SupportMessage.id)))
    return Thread(ticket, msgs)


async def my_thread(session: AsyncSession, user_id: int) -> Thread | None:
    ticket = await open_of(session, user_id)
    if ticket is None:
        ticket = await session.scalar(select(SupportTicket).where(SupportTicket.user_id == user_id).order_by(SupportTicket.id.desc()).limit(1))
    return await thread(session, ticket.id) if ticket else None


async def reply(session: AsyncSession, staff_id: int, ticket_id: int, text: str | None) -> int:
    """Ответ сотрудника. → id игрока (для пуша). Коммитит."""
    t = _clean(text)
    ticket = await session.get(SupportTicket, ticket_id, with_for_update=True)
    if ticket is None:
        raise SupportError("gone")
    ticket.status, ticket.updated_at = ANSWERED, datetime.now(timezone.utc)
    session.add(SupportMessage(ticket_id=ticket_id, author_id=staff_id, staff=True, text=t))
    user_id = ticket.user_id
    await session.commit()
    return user_id


async def close(session: AsyncSession, ticket_id: int) -> int | None:
    ticket = await session.get(SupportTicket, ticket_id, with_for_update=True)
    if ticket is None:
        return None
    ticket.status = CLOSED
    user_id = ticket.user_id
    await session.commit()
    return user_id


async def queue(session: AsyncSession, status: str | None = OPEN, page: int = 0) -> tuple[list[tuple[SupportTicket, str]], int]:
    """Обращения для сотрудников (по умолчанию — ждут ответа), свежие сверху: (обращение, первая строка последнего
    сообщения игрока) и всего ждут ответа."""
    stmt = select(SupportTicket).order_by(SupportTicket.updated_at.desc()).offset(page * PAGE).limit(PAGE)
    if status:
        stmt = stmt.where(SupportTicket.status == status)
    tickets = list(await session.scalars(stmt))
    previews = []
    for t in tickets:
        last = await session.scalar(select(SupportMessage.text).where(SupportMessage.ticket_id == t.id, SupportMessage.staff.is_(False))
                                    .order_by(SupportMessage.id.desc()).limit(1))
        previews.append((t, (last or "").split("\n")[0][:60]))
    waiting = int(await session.scalar(select(func.count()).select_from(SupportTicket).where(SupportTicket.status == OPEN)) or 0)
    return previews, waiting
