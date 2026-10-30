"""Вебхук ЮKassa для оплаты по СБП (2026-10-30). URL для кабинета ЮKassa (Интеграция →
HTTP-уведомления, событие payment.succeeded и payment.canceled):
https://lbp.universanimeplanet.ru/api/payments/yookassa

Без initData — запрос приходит от серверов ЮKassa. Телу уведомления не доверяем: берём
только id платежа и перечитываем его из API ЮKassa своими ключами (services/sbp)."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_session
from bot.config.settings import get_settings
from bot.services import sbp as sbp_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/yookassa")
async def yookassa_webhook(request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        payment_id = str((await request.json())["object"]["id"])
    except Exception:
        return {"ok": True}  # не уведомление ЮKassa — молча 200, повторять нечего
    if not sbp_service.enabled():
        return {"ok": True}
    bot = Bot(token=get_settings().bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await sbp_service.handle_notification(session, bot, payment_id)
    except sbp_service.YooKassaError as exc:
        log.warning("YooKassa webhook %s: %s", payment_id, exc)
        raise HTTPException(503, "retry later") from exc  # ЮKassa повторит уведомление
    finally:
        await bot.session.close()
    return {"ok": True}
