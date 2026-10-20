"""Крутки за тикеты — получение уникального персонажа (хендлеры).

Кнопка «🃏 Вербовка уника» на экране вербовки и «🃏 Крутить ещё» под результатом — один
и тот же callback. Каждая крутка — новое сообщение с результатом (кнопка «ещё» всегда под
последним), как в UAP.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.absolute import ABSOLUTES
from bot.services.position_skill import card_skill_lines
from bot.texts.absolute import PERKS
from bot.texts.card import POSITION_LABELS
from bot.texts.gacha import ROLL_PERK_LINE, ROLL_SKILLS_LINE, ROLL_SKILLS_TAIL
from bot.constant.gacha import CB_GACHA_ROLL, CB_GACHA_ROLL_MANY
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


# --- массовое открытие вводом количества (пользователь 2026-10-21) ---


@router.callback_query(F.data == CB_GACHA_ROLL_MANY)
async def cb_gacha_roll_many(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    from bot.config.card import GACHA_MASS_MAX
    from bot.constant.recruit import CB_RECRUIT_OPEN
    from bot.keyboards.common import back_menu
    from bot.services.ticket import get_status
    from bot.states.gacha import GachaStates
    from bot.texts.gacha import ROLL_MANY_PROMPT

    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    status = await get_status(session, callback.from_user.id)
    await session.commit()
    await state.set_state(GachaStates.waiting_count)
    await callback.answer()
    await callback.message.answer(
        ROLL_MANY_PROMPT.format(count=format_number(status.count), max=GACHA_MASS_MAX),
        reply_markup=back_menu(CB_RECRUIT_OPEN),
    )


async def on_gacha_count(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    from collections import Counter

    from bot.config.card import GACHA_MASS_MAX, RARITY_CHANCE_PERCENT
    from bot.services.gacha import roll_many
    from bot.texts.gacha import (
        ROLL_MANY_FREE, ROLL_MANY_INVALID, ROLL_MANY_RARITY_LINE, ROLL_MANY_RESULT, ROLL_MANY_STOPPED,
    )

    raw = (message.text or "").strip().replace(" ", "")
    if not raw.isdigit() or int(raw) < 1:
        await message.answer(ROLL_MANY_INVALID)
        return
    count = min(int(raw), GACHA_MASS_MAX)
    await state.clear()
    try:
        results = await roll_many(session, redis, message.from_user.id, count)
    except RollBusyError:
        await message.answer(ROLL_BUSY)
        return
    except NoTicketsError as exc:
        await message.answer(NO_TICKETS.format(countdown=format_countdown(exc.status.next_in_seconds or 0)))
        return

    from bot.config.card import CARD_BY_CODE

    order = {k: i for i, k in enumerate(RARITY_CHANCE_PERCENT)}  # от частой к редкой
    drawn = [(CARD_BY_CODE[code], n) for code, n in results.counts.items() if code in CARD_BY_CODE]
    rarities = Counter()
    for card, n in drawn:
        rarities[card.rarity] += n
    rarity_lines = "\n".join(
        ROLL_MANY_RARITY_LINE.format(rarity=RARITY_LABELS.get(k, k), count=format_number(rarities[k]))
        for k in sorted(rarities, key=lambda k: order.get(k, -1), reverse=True)
    )
    new_cards = sorted((c for c, _ in drawn if c.code in results.new_codes), key=lambda c: order.get(c.rarity, -1), reverse=True)
    new_list = (": " + ", ".join(esc(c.name) for c in new_cards[:15]) + ("…" if len(new_cards) > 15 else "")) if new_cards else ""
    best = max(drawn, key=lambda d: (order.get(d[0].rarity, -1), d[0].power))[0]
    tickets = results.tickets
    text = ROLL_MANY_RESULT.format(
        count=format_number(results.opened), rarities=rarity_lines, new=len(new_cards), new_list=new_list,
        free_line=ROLL_MANY_FREE.format(free=format_number(results.free)) if results.free else "",
        best=esc(card_label(best)), tickets_line=tickets_line(tickets.count, tickets.cap, tickets.next_in_seconds),
        stopped=ROLL_MANY_STOPPED if results.opened < count else "",
    )
    photo = await get_card_photo(redis, best)
    if photo is None or len(text) > 1000:
        await message.answer(text, reply_markup=roll_result_menu())
        return
    sent = await message.answer_photo(photo, caption=text, reply_markup=roll_result_menu())
    await remember_card_photo(redis, best, sent)


def _register_count_handler() -> None:
    from bot.states.gacha import GachaStates

    router.message.register(on_gacha_count, GachaStates.waiting_count)


_register_count_handler()
