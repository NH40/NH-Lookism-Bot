"""Коллекция уникальных персонажей — список, карточка, распределение по лагерям и позициям (хендлеры).

Вход — «🃏 Уники» на экране банды и «📚 Коллекция» под результатом крутки. Карточка уника:
копии по лагерям (перенос 1 / всех), постановка на допустимую позицию отряда. Экран состава
(все 9 позиций) — `handlers/gang/lineup.py`.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.card import CARD_BY_CODE
from bot.constant.absolute import ABS_STYLIST, ABSOLUTES, CB_STYLIST_PICK_PREFIX
from bot.keyboards.collection import absolute_menu
from bot.services.absolute import StylistError, set_style_pick, style_pick
from bot.texts.absolute import PERK_BLOCK, PERKS, STYLIST_PICKED, STYLIST_PROMPT, STYLIST_SET_ALERT
from bot.constant.collection import (
    AMOUNT_ALL,
    AMOUNT_ONE,
    CB_COLLECTION_ASSIGN_PREFIX,
    CB_COLLECTION_CAMP_MOVE_PREFIX,
    CB_COLLECTION_CARD_PREFIX,
    CB_COLLECTION_MOVE_PREFIX,
    CB_COLLECTION_OPEN,
    CB_COLLECTION_PAGE_PREFIX,
)
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
from bot.constant.card import RARITY_ORDER
from bot.keyboards.collection import card_menu, collection_menu, rarities_menu
from bot.services.card import (
    CollectionEntry,
    InvalidCampMoveError,
    NoFreeCopyError,
    PositionNotAllowedError,
    UnknownCardError,
    assign_position,
    get_collection,
    get_entry,
    move_all_copies,
    move_copies,
)
from bot.services.gang import get_gang
from bot.services.ticket import get_status as get_ticket_status
from bot.texts.card import POSITION_LABELS, RARITY_EMOJI, RARITY_LABELS, card_label, positions_label
from bot.texts.collection import (
    ASSIGNED,
    ASSIGNED_REPLACED,
    CARD_BTN,
    CARD_GONE,
    CARDS_MOVED,
    CARDS_NOTHING_TO_MOVE,
    CARD_SCREEN,
    COLLECTION_EMPTY,
    COLLECTION_HEADER,
    MOVED,
    NO_FREE_COPY,
    NOTHING_TO_MOVE,
    POSITION_NOT_ALLOWED,
    RARITY_BTN,
    RARITY_SCREEN,
)
from bot.texts.gacha import tickets_line
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.card_media import get_card_photo, remember_card_photo
from bot.utils.formatting import esc, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="collection")


async def _render_collection(session: AsyncSession, user_id: int, page: int = 0, rarity: str | None = None):
    """Без `rarity` — экран выбора редкости (как в 1.0), иначе — карты этой редкости."""
    entries = await get_collection(session, user_id)
    if rarity is not None:
        picked = [e for e in entries if e.card.rarity == rarity]
        if picked:
            text = RARITY_SCREEN.format(
                emoji=RARITY_EMOJI[rarity], label=RARITY_LABELS[rarity], cards=len(picked),
                copies=format_number(sum(e.total for e in picked)),
            )
            buttons = [(e.card.code, CARD_BTN.format(label=card_label(e.card), total=format_number(e.total))) for e in picked]
            return text, collection_menu(buttons, page, rarity)
    tickets = await get_ticket_status(session, user_id)
    line = tickets_line(tickets.count, tickets.cap, tickets.next_in_seconds)
    if not entries:
        return COLLECTION_EMPTY.format(tickets_line=line), rarities_menu([])
    army = sum(e.army for e in entries)
    placed = sum(len(e.placed) for e in entries)
    text = COLLECTION_HEADER.format(
        attack=format_number(sum(e.attack for e in entries)),
        defense=format_number(sum(e.defense for e in entries)),
        cards=len(entries),
        copies=format_number(army + placed),
        army=format_number(army),
        placed=placed,
        tickets_line=line,
    )
    by_rarity: dict[str, list[CollectionEntry]] = {}
    for e in entries:
        by_rarity.setdefault(e.card.rarity, []).append(e)
    rarities = [
        (r, RARITY_BTN.format(
            emoji=RARITY_EMOJI[r], label=RARITY_LABELS[r], cards=len(by_rarity[r]),
            copies=format_number(sum(e.total for e in by_rarity[r])),
        ))
        for r in reversed(RARITY_ORDER) if r in by_rarity
    ]
    return text, rarities_menu(rarities)


def _render_card(entry: CollectionEntry, pick: str | None = None):
    card = entry.card
    text = CARD_SCREEN.format(
        label=esc(card_label(card)),
        rarity=RARITY_LABELS[card.rarity],
        power=format_number(card.power),
        positions=positions_label(card.positions),
        total=format_number(entry.total),
        attack=format_number(entry.attack),
        defense=format_number(entry.defense),
        placed=positions_label(entry.placed),
    )
    if card.code in ABSOLUTES:  # пассивка за обладание: не воюет, позиций и лагерей нет
        text += PERK_BLOCK.format(perk=PERKS.get(card.code, ""))
        if card.code == ABS_STYLIST:
            text += STYLIST_PICKED.format(name=esc(CARD_BY_CODE[pick].name)) if pick in CARD_BY_CODE else STYLIST_PROMPT
        return text, absolute_menu(card.code, rarity=card.rarity, pick=pick)
    # Поставить можно на допустимую позицию, где эта карта ещё не стоит, при свободной копии.
    assignable = [p for p in card.positions if p not in entry.placed] if entry.army > 0 else []
    return text, card_menu(card.code, assignable=assignable, rarity=card.rarity)


async def _send_card_screen(message: Message, redis: Redis, entry: CollectionEntry, pick: str | None = None) -> None:
    """Экран карты — фото карточки с подписью. Сообщение уже фото (это экран этой же карты:
    перенос/постановка) — меняем только подпись и кнопки. Иначе (пришли из текстового
    списка) — текст в фото не редактируется (правило 12), поэтому удаляем и шлём заново."""
    text, markup = _render_card(entry, pick)
    if message.photo:
        try:
            await message.edit_caption(caption=text, reply_markup=markup)
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                raise
        return
    photo = await get_card_photo(redis, entry.card)
    if photo is None:
        await safe_edit_text(message, text, reply_markup=markup)
        return
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    sent = await message.answer_photo(photo, caption=text, reply_markup=markup)
    await remember_card_photo(redis, entry.card, sent)


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


@router.callback_query(F.data == CB_COLLECTION_OPEN)
async def cb_collection_open(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    text, markup = await _render_collection(session, callback.from_user.id, 0)
    if callback.message.photo:
        # Пришли из-под результата крутки (фото) — не стираем его, список новым сообщением.
        await callback.message.answer(text, reply_markup=markup)
    else:
        await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_COLLECTION_PAGE_PREFIX))
async def cb_collection_page(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    rarity, _, page_raw = callback.data.removeprefix(CB_COLLECTION_PAGE_PREFIX).rpartition(":")
    try:
        page = int(page_raw)
    except ValueError:
        page = 0
    await callback.answer()
    text, markup = await _render_collection(session, callback.from_user.id, page, rarity or None)
    await safe_edit_text(callback.message, text, reply_markup=markup)


async def _show_card_or_list(callback: CallbackQuery, session: AsyncSession, redis: Redis, code: str) -> None:
    entry = await get_entry(session, callback.from_user.id, code)
    if entry is None:
        text, markup = await _render_collection(session, callback.from_user.id, 0)
        await safe_edit_text(callback.message, text, reply_markup=markup)
    else:
        await _send_card_screen(callback.message, redis, entry, await style_pick(session, callback.from_user.id))


@router.callback_query(F.data.startswith(CB_COLLECTION_CARD_PREFIX))
async def cb_collection_card(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    code = callback.data.removeprefix(CB_COLLECTION_CARD_PREFIX)
    entry = await get_entry(session, callback.from_user.id, code)
    if entry is None:
        await callback.answer(CARD_GONE, show_alert=True)
        text, markup = await _render_collection(session, callback.from_user.id, 0)
        await safe_edit_text(callback.message, text, reply_markup=markup)
        return
    await callback.answer()
    await _send_card_screen(callback.message, redis, entry, await style_pick(session, callback.from_user.id))


@router.callback_query(F.data.startswith(CB_COLLECTION_MOVE_PREFIX))
async def cb_collection_move(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    try:
        code, from_camp, amount_raw = callback.data.removeprefix(CB_COLLECTION_MOVE_PREFIX).rsplit(":", 2)
        if amount_raw not in (AMOUNT_ONE, AMOUNT_ALL):
            raise ValueError(amount_raw)
        to_camp = CAMP_DEFENSE if from_camp == CAMP_ATTACK else CAMP_ATTACK
        moved = await move_copies(
            session, callback.from_user.id, code, from_camp, to_camp, 1 if amount_raw == AMOUNT_ONE else None
        )
    except (ValueError, InvalidCampMoveError):
        await callback.answer()
        return
    # Popup — без HTML.
    await callback.answer(MOVED.format(moved=format_number(moved)) if moved else NOTHING_TO_MOVE, show_alert=not moved)
    if moved:
        await _show_card_or_list(callback, session, redis, code)


@router.callback_query(F.data.startswith(CB_COLLECTION_ASSIGN_PREFIX))
async def cb_collection_assign(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    try:
        code, position = callback.data.removeprefix(CB_COLLECTION_ASSIGN_PREFIX).rsplit(":", 1)
        replaced = await assign_position(session, callback.from_user.id, position, code)
    except ValueError:
        await callback.answer()
        return
    except (UnknownCardError, PositionNotAllowedError):
        await callback.answer(POSITION_NOT_ALLOWED, show_alert=True)
        return
    except NoFreeCopyError:
        await callback.answer(NO_FREE_COPY, show_alert=True)
        return

    entry = await get_entry(session, callback.from_user.id, code)
    name = entry.card.name if entry else code
    if replaced is not None:
        await callback.answer(ASSIGNED_REPLACED.format(card=name, position=POSITION_LABELS[position], old=replaced.name))
    else:
        await callback.answer(ASSIGNED.format(card=name, position=POSITION_LABELS[position]))
    await _show_card_or_list(callback, session, redis, code)


@router.callback_query(F.data.startswith(CB_COLLECTION_CAMP_MOVE_PREFIX))
async def cb_collection_camp_move(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    try:
        from_camp, to_camp, percent_raw = callback.data.removeprefix(CB_COLLECTION_CAMP_MOVE_PREFIX).split(":")
        moved = await move_all_copies(session, callback.from_user.id, from_camp, to_camp, int(percent_raw))
    except (ValueError, InvalidCampMoveError):
        await callback.answer()
        return
    # Popup — без HTML.
    await callback.answer(CARDS_MOVED.format(moved=format_number(moved)) if moved else CARDS_NOTHING_TO_MOVE, show_alert=not moved)
    if moved:
        text, markup = await _render_collection(session, callback.from_user.id)
        await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_STYLIST_PICK_PREFIX))
async def cb_stylist_pick(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    code = callback.data.removeprefix(CB_STYLIST_PICK_PREFIX)
    try:
        await set_style_pick(session, callback.from_user.id, code)
    except StylistError:
        await callback.answer()
        return
    await callback.answer(STYLIST_SET_ALERT.format(name=CARD_BY_CODE[code].name))
    entry = await get_entry(session, callback.from_user.id, ABS_STYLIST)
    if entry is not None:
        await _send_card_screen(callback.message, redis, entry, code)
