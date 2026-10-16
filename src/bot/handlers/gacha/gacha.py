"""Крутки за тикеты — получение уникального персонажа (хендлеры).

Кнопка «🃏 Вербовка уника» на экране вербовки и «🃏 Крутить ещё» под результатом — один
и тот же callback. Каждая крутка — новое сообщение с результатом (кнопка «ещё» всегда под
последним), как в UAP.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.absolute import ABSOLUTES
from bot.services.position_skill import card_skill_lines
from bot.texts.absolute import PERKS
from bot.texts.card import POSITION_LABELS
from bot.texts.gacha import ROLL_PERK_LINE, ROLL_SKILLS_LINE, ROLL_SKILLS_TAIL
from bot.constant.gacha import CB_GACHA_ROLL
from bot.keyboards.gacha import roll_result_menu
from bot.services.gacha import NoTicketsError, RollBusyError, roll
from bot.services.gang import get_gang
from bot.texts.card import RARITY_LABELS, card_label, positions_label
from bot.texts.gacha import COPIES_DUPLICATE, COPIES_NEW, NO_TICKETS, ROLL_BUSY, ROLL_RESULT, tickets_line
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.card_media import get_card_photo, remember_card_photo
from bot.utils.formatting import esc, format_countdown, format_number

router = Router(name="gacha")


def _skills_line(card) -> str:
    """Навыки выпавшей карты по позициям (только имена — подпись фото ограничена) или перк абсолюта."""
    if card.code in ABSOLUTES:
        return ROLL_PERK_LINE.format(perk=esc(PERKS.get(card.code, "")))
    lines = []
    for position in card.positions:
        skills = card_skill_lines(card, position)
        if skills:
            lines.append(ROLL_SKILLS_LINE.format(position=POSITION_LABELS[position], names=", ".join(esc(x.name) for x in skills)))
    return "".join(lines) + (ROLL_SKILLS_TAIL if lines else "")


@router.callback_query(F.data == CB_GACHA_ROLL)
async def cb_gacha_roll(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        result = await roll(session, redis, callback.from_user.id)
    except RollBusyError:
        await callback.answer(ROLL_BUSY)
        return
    except NoTicketsError as exc:
        # Popup — без HTML.
        await callback.answer(
            NO_TICKETS.format(countdown=format_countdown(exc.status.next_in_seconds or 0)), show_alert=True
        )
        return

    card, tickets = result.card, result.tickets
    text = ROLL_RESULT.format(
        label=esc(card_label(card)),
        rarity=RARITY_LABELS[card.rarity],
        power=format_number(card.power),
        positions=positions_label(card.positions),
        copies_line=COPIES_NEW if result.copies == 1 else COPIES_DUPLICATE.format(copies=result.copies),
        tickets_line=tickets_line(tickets.count, tickets.cap, tickets.next_in_seconds),
        skills_line=_skills_line(card),
    )
    await callback.answer()
    # Картинка карты (пока карточки 1.0 из assets/) — фото с подписью; нет картинки — текстом.
    photo = await get_card_photo(redis, card)
    if photo is None:
        await callback.message.answer(text, reply_markup=roll_result_menu())
        return
    sent = await callback.message.answer_photo(photo, caption=text, reply_markup=roll_result_menu())
    await remember_card_photo(redis, card, sent)
