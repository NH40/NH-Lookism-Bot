"""Банда игрока — название, состав (9 позиций), статисты (лагеря) (хендлеры).

Пока единственный флоу — ввод названия банды сразу после выбора города при онбординге
(raw-notes «Карта»: «банда начинается с названия»). `prompt_gang_name()` — публичная
функция домена (не `_prompt`), переиспользуется `handlers/start` (тот же паттерн, что
`show_profile` у `handlers/profile`).
"""
from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.profile import show_profile
from bot.services.gang import GangAlreadyExistsError, InvalidGangNameError, create_gang
from bot.states.gang import GangStates
from bot.texts.gang import NAME_CONFIRMED, NAME_PROMPT, NAME_TOO_LONG, NAME_TOO_SHORT

router = Router(name="gang")


async def prompt_gang_name(message: Message, state: FSMContext) -> None:
    await state.set_state(GangStates.waiting_name)
    await message.answer(NAME_PROMPT)


@router.message(GangStates.waiting_name)
async def on_gang_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        gang = await create_gang(session, message.from_user.id, message.text or "")
    except InvalidGangNameError as exc:
        await message.answer(NAME_TOO_SHORT if exc.reason == "too_short" else NAME_TOO_LONG)
        return
    except GangAlreadyExistsError:
        # Гонка/повторный заход в это состояние у игрока, у которого банда уже есть —
        # ничего не создаём повторно, просто продолжаем в профиль как обычно.
        await state.clear()
        await show_profile(message, session, message.from_user.id)
        return

    await state.clear()
    await message.answer(NAME_CONFIRMED.format(name=gang.name))
    await show_profile(message, session, message.from_user.id)
