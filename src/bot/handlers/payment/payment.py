"""Платежи (хендлеры): pre_checkout и зачисление успешной оплаты — как в UAP."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.donate import PAYLOAD_DONATE_PREFIX
from bot.services.donate import credit_payment
from bot.texts.donate import PAYMENT_DONE
from bot.utils.formatting import format_number

router = Router(name="payment")

_KOPECKS_PER_RUB = 100


@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    # Инвойсы создаём только сами — сумма валидна по построению. Отвечаем сразу, без БД:
    # у Telegram SLA 10 секунд, иначе платёж отменится.
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, session: AsyncSession) -> None:
    payment = message.successful_payment
    if not payment.invoice_payload.startswith(PAYLOAD_DONATE_PREFIX):
        return
    coins = await credit_payment(
        session,
        message.from_user.id,
        payment.telegram_payment_charge_id,
        payment.provider_payment_charge_id or "",
        payment.total_amount // _KOPECKS_PER_RUB,
    )
    if coins is not None:  # None — Telegram передоставил апдейт, уже зачислено
        await message.answer(PAYMENT_DONE.format(coins=format_number(coins)))
