"""Промокоды (игрок): /promo КОД или /promo, затем код сообщением."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.user import get_by_id
from bot.services import promo as promo_service
from bot.states.promo import PromoStates
from bot.texts.promo import (
    ALREADY_USED,
    EXHAUSTED,
    EXPIRED,
    INACTIVE,
    NEED_START,
    NOT_ALLOWED,
    NOT_FOUND,
    PROMPT,
    REDEEMED,
)
from bot.texts.resource import amount_label

router = Router(name="promo")

_ERRORS = {
    promo_service.PromoNotFoundError: NOT_FOUND,
    promo_service.PromoInactiveError: INACTIVE,
    promo_service.PromoExpiredError: EXPIRED,
    promo_service.PromoExhaustedError: EXHAUSTED,
    promo_service.PromoAlreadyUsedError: ALREADY_USED,
    promo_service.PromoNotAllowedError: NOT_ALLOWED,
}


def _reward_text(reward: dict[str, int]) -> str:
    return "\n".join(f"{'+' if v > 0 else '−'}{amount_label(k, abs(v))}" for k, v in reward.items())


async def _redeem(message: Message, session: AsyncSession, code: str) -> None:
    user = await get_by_id(session, message.from_user.id)
    if user is None:
        await message.answer(NEED_START)
        return
    try:
        reward = await promo_service.redeem(session, user, code)
    except promo_service.PromoError as exc:
        await message.answer(_ERRORS.get(type(exc), NOT_FOUND))
        return
    await message.answer(REDEEMED.format(reward=_reward_text(reward)))


@router.message(Command("promo"))
async def cmd_promo(message: Message, command: CommandObject, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    code = (command.args or "").strip()
    if not code:
        await state.set_state(PromoStates.waiting_code)
        await message.answer(PROMPT)
        return
    await _redeem(message, session, code)


@router.message(StateFilter(PromoStates.waiting_code), F.text, ~F.text.startswith("/"))
async def apply_code(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await _redeem(message, session, message.text)
