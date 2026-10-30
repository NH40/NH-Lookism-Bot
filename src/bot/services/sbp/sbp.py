"""Оплата по СБП через API ЮKassa (2026-10-30, третий способ доната рядом с картой в Telegram).

Поток: игрок выбрал сумму и «СБП» → `create()` заводит платёж в ЮKassa и строку
`sbp_payments` → игрок платит в приложении банка → ЮKassa шлёт вебхук на API
(`api/routers/payments.py`) → `settle()`. Страховка, если вебхук потерялся: фоновая
проверка `sweep()` раз в минуту и кнопка «Я оплатил» (`refresh()`).

Содержимому вебхука не доверяем: по id из уведомления платёж всегда перечитывается из API
ЮKassa с нашими ключами — подделать «оплачено» снаружи нельзя. Зачисление — тот же
`services/donate.credit_payment`, что у карты (донат-коины, запись в payments).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.donate import SBP_POLL_MAX_AGE_MINUTES
from bot.config.settings import get_settings
from bot.constant.donate import SBP_METADATA_BOT, SBP_STATUS_CANCELED, SBP_STATUS_SUCCEEDED
from bot.db.models.donate import SbpPayment
from bot.db.repositories import sbp_payment as sbp_repo
from bot.services.donate import credit_payment
from bot.services.sbp.client import YkPayment, YooKassaError, create_payment, get_payment
from bot.texts.donate import INVOICE_DESCRIPTION, PAYMENT_DONE, SBP_PAID_SCREEN
from bot.utils.formatting import format_number

log = logging.getLogger(__name__)

_SWEEP_BATCH = 50


def enabled() -> bool:
    s = get_settings()
    return bool(s.yookassa_shop_id and s.yookassa_secret_key)


@dataclass(frozen=True, slots=True)
class Settled:
    payment: SbpPayment
    coins: int | None  # None — уже было зачислено раньше


async def create(session: AsyncSession, bot: Bot, user_id: int, amount_rub: int) -> SbpPayment:
    """Завести платёж в ЮKassa и строку счёта. Коммитит. YooKassaError — ЮKassa отказала."""
    me = await bot.me()
    payment = await create_payment(
        amount_rub,
        INVOICE_DESCRIPTION.format(amount=amount_rub),
        return_url=f"https://t.me/{me.username}",
        metadata={"bot": SBP_METADATA_BOT, "user_id": str(user_id)},
    )
    if not payment.confirmation_url:
        raise YooKassaError("нет ссылки на оплату")
    row = await sbp_repo.create(
        session, yookassa_id=payment.id, user_id=user_id, amount_rub=amount_rub,
        confirmation_url=payment.confirmation_url, chat_id=None, message_id=None,
    )
    await session.commit()
    return row


async def attach_message(session: AsyncSession, row: SbpPayment, chat_id: int, message_id: int) -> None:
    row.chat_id, row.message_id = chat_id, message_id
    await session.commit()


async def settle(session: AsyncSession, yk: YkPayment) -> Settled | None:
    """Применить статус платежа из ЮKassa. → Settled, если ЭТОТ вызов зачислил оплату; иначе
    None (чужой бот, ещё не оплачен, уже зачислено, отменён)."""
    if yk.metadata.get("bot") != SBP_METADATA_BOT:
        return None
    if yk.status == "succeeded" and yk.paid:
        row = await sbp_repo.mark_succeeded(session, yk.id)
        if row is None:
            await session.rollback()
            return None
        if yk.amount_rub < row.amount_rub:  # не должно случиться — сумму задаём сами
            log.error("SBP %s: оплачено %s ₽ вместо %s ₽", yk.id, yk.amount_rub, row.amount_rub)
            await session.rollback()
            return None
        coins = await credit_payment(session, row.user_id, f"yk:{yk.id}", yk.id, row.amount_rub)
        if coins is None:  # платёж уже записан в payments (credit_payment откатил) — фиксируем статус
            row = await sbp_repo.mark_succeeded(session, yk.id)
            await session.commit()
            return None
        return Settled(row, coins)
    if yk.status == "canceled":
        await sbp_repo.mark_open_as(session, yk.id, SBP_STATUS_CANCELED)
        await session.commit()
    return None


async def refresh(session: AsyncSession, row: SbpPayment) -> tuple[str, Settled | None]:
    """Кнопка «Я оплатил»: перечитать платёж. → (статус счёта после проверки, Settled|None)."""
    if row.status == SBP_STATUS_SUCCEEDED:
        return row.status, None
    yk = await get_payment(row.yookassa_id)
    result = await settle(session, yk)
    await session.refresh(row)
    return row.status, result


async def announce(bot: Bot, result: Settled) -> None:
    """Сообщить игроку о зачислении и снять кнопки со счёта. Best-effort."""
    if result.coins is None:
        return
    row = result.payment
    coins = format_number(result.coins)
    try:
        await bot.send_message(row.user_id, PAYMENT_DONE.format(coins=coins))
    except TelegramAPIError:
        pass  # игрок мог заблокировать бота — коины уже зачислены
    if row.chat_id and row.message_id:
        try:
            await bot.edit_message_text(
                SBP_PAID_SCREEN.format(amount=format_number(row.amount_rub), coins=coins),
                chat_id=row.chat_id, message_id=row.message_id,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[]),  # правило 11
            )
        except TelegramAPIError:
            pass


async def handle_notification(session: AsyncSession, bot: Bot, payment_id: str) -> None:
    """Вебхук ЮKassa: перечитать платёж по id и применить. YooKassaError пробрасывается —
    API ответит 5xx, и ЮKassa повторит уведомление позже."""
    result = await settle(session, await get_payment(payment_id))
    if result is not None:
        await announce(bot, result)


async def sweep(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Фоновая страховка к вебхуку: спросить ЮKassa о незакрытых свежих счетах."""
    border = datetime.now(timezone.utc) - timedelta(minutes=SBP_POLL_MAX_AGE_MINUTES)
    async with session_factory() as session:
        await sbp_repo.expire_older(session, border)
        await session.commit()
        pending = [(r.yookassa_id) for r in await sbp_repo.list_pending(session, border, _SWEEP_BATCH)]
    for yookassa_id in pending:
        try:
            yk = await get_payment(yookassa_id)
        except YooKassaError:
            continue
        async with session_factory() as session:
            result = await settle(session, yk)
        if result is not None:
            await announce(bot, result)
