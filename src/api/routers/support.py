"""API-роутер Mini App: тикеты в поддержку — игрок пишет, сотрудники (саппорт, модераторы, админы) отвечают."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.push import get_bot
from api.routers._common import bad, require_user
from api.routers.admin import access
from bot.constant.admin import SECTION_SUPPORT
from bot.services import support as svc
from bot.utils.formatting import esc
from bot.utils.notify import notify

router = APIRouter(prefix="/api", tags=["support"])


class TextIn(BaseModel):
    text: str


def _thread(th) -> dict | None:
    if th is None:
        return None
    return {"id": th.ticket.id, "status": th.ticket.status, "user_id": th.ticket.user_id,
            "messages": [{"staff": m.staff, "text": m.text, "at": m.created_at.isoformat()} for m in th.messages]}


@router.get("/support")
async def my_support(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id, need_city=False)
    return {"thread": _thread(await svc.my_thread(session, user_id)), "max": svc.MAX_TEXT}


@router.post("/support")
async def write(body: TextIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id, need_city=False)
    try:
        t = await svc.write(session, user_id, body.text)
    except svc.SupportError:
        raise bad(f"Сообщение — от 1 до {svc.MAX_TEXT} символов.")
    return {"message": f"Отправлено в поддержку (обращение #{t.id})."}


@router.get("/admin/support")
async def queue(status: str = "open", user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_SUPPORT)
    items, waiting = await svc.queue(session, None if status == "all" else status)
    return {"waiting": waiting, "items": [{"id": t.id, "user_id": t.user_id, "status": t.status, "preview": p} for t, p in items]}


@router.get("/admin/support/{ticket_id}")
async def ticket(ticket_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_SUPPORT)
    th = await svc.thread(session, ticket_id)
    if th is None:
        raise bad("Обращение не найдено.")
    return _thread(th)


@router.post("/admin/support/{ticket_id}/reply")
async def reply(ticket_id: int, body: TextIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_SUPPORT)
    try:
        player = await svc.reply(session, user_id, ticket_id, body.text)
    except svc.SupportError:
        raise bad("Не получилось — обращение пропало или текст пустой.")
    await notify(get_bot(), player, f"🛡 <b>Ответ поддержки</b> (обращение #{ticket_id}):\n{esc(body.text)}\n\nОтветить — /support")
    return {"message": "Ответ отправлен."}


@router.post("/admin/support/{ticket_id}/close")
async def close(ticket_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_SUPPORT)
    player = await svc.close(session, ticket_id)
    if player:
        await notify(get_bot(), player, f"🔒 Обращение #{ticket_id} закрыто. Если вопрос остался — напиши снова: /support")
    return {"message": "Закрыто."}
