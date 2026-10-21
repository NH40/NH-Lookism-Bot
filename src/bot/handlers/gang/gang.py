"""Банда игрока — название, состав (9 позиций), статисты (лагеря) (хендлеры).

Три флоу: ввод названия банды сразу после выбора города при онбординге (raw-notes
«Карта»: «банда начинается с названия»), экран банды — армия по лагерям атака/защита
с быстрым переводом доли всей армии (raw-notes «Банда»: «распределить статистов на две
лагеря»), и ручная сборка лагерей по отрядам — точное число бойцов конкретного отряда
в нужный лагерь (запрос пользователя 2026-09-29). Состав из 9 позиций и уникальная коллекция — ждут уникальных персонажей
(домены `card`/`gacha`). `prompt_gang_name()` — публичная функция домена,
переиспользуется `handlers/start`.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE, CAMPS
from bot.constant.gang import (
    AMOUNT_ALL,
    AMOUNT_HALF,
    CB_GANG_BACK,
    CB_GANG_CAMP_MOVE_PREFIX,
    CB_GANG_DELETE_ASK,
    CB_GANG_DELETE_CONFIRM,
    CB_GANG_OPEN,
    CB_GANG_SQUAD_CUSTOM_PREFIX,
    CB_GANG_SQUAD_MOVE_PREFIX,
    CB_GANG_SQUAD_PREFIX,
    CB_GANG_SQUADS_PREFIX,
)
from bot.handlers.profile import show_profile
from bot.keyboards.gang import delete_confirm_menu, gang_menu, squad_back_menu, squad_key, squad_menu, squads_menu
from bot.keyboards.start import country_menu
from bot.services.extra import (
    InvalidCampMoveError,
    Squad,
    get_army_stats,
    get_squad,
    list_army_squads as list_squads,
    move_between_camps,
    move_squad,
)
from bot.services.gang import (
    ConfirmExpiredError,
    GangAlreadyExistsError,
    InvalidGangNameError,
    confirm_delete,
    create_gang,
    get_gang,
    request_delete,
)
from bot.db.repositories.user import get_by_id
from bot.handlers.bloodline import prompt_bloodline
from bot.states.gang import GangStates
from bot.texts.gang import (
    CAMP_MOVED,
    CAMP_NOTHING_TO_MOVE,
    DELETE_CONFIRM_SCREEN,
    DELETE_DONE,
    DELETE_EXPIRED,
    DIRECTION_TO_ATTACK,
    DIRECTION_TO_DEFENSE,
    GANG_SCREEN,
    NAME_CONFIRMED,
    NAME_PROMPT,
    NAME_TOO_LONG,
    NAME_TOO_SHORT,
    SQUAD_AMOUNT_INVALID,
    SQUAD_AMOUNT_PROMPT,
    SQUAD_BTN,
    SQUAD_GONE,
    SQUAD_MOVED_MESSAGE,
    SQUAD_NOTHING_MOVED_MESSAGE,
    SQUAD_NOTHING_TO_MOVE,
    SQUAD_SCREEN,
    SQUADS_EMPTY,
    SQUADS_HEADER,
    squad_title,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.start import CHOOSE_COUNTRY
from bot.utils.formatting import esc, format_number
from bot.utils.safe_edit import safe_clear_markup, safe_edit_text

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
    await message.answer(NAME_CONFIRMED.format(name=esc(gang.name)))
    # Следующий шаг онбординга — родословная (выбор навсегда), профиль — после неё. После
    # удаления банды родословная остаётся (`services/gang/reset`) — повторно её не спрашиваем,
    # иначе игрок застревал: любой выбор отклонялся как «уже выбрана» (баг 2026-10-21).
    user = await get_by_id(session, message.from_user.id)
    if user is not None and user.bloodline is not None:
        await show_profile(message, session, message.from_user.id)
        return
    await prompt_bloodline(message)


async def _render_gang_screen(session: AsyncSession, user_id: int, gang_name: str) -> str:
    army = await get_army_stats(session, user_id)
    return GANG_SCREEN.format(
        name=esc(gang_name),
        attack_quantity=format_number(army.attack.quantity),
        attack_power=format_number(army.attack.power),
        defense_quantity=format_number(army.defense.quantity),
        defense_power=format_number(army.defense.power),
    )


@router.callback_query(F.data == CB_GANG_OPEN)
async def cb_gang_open(callback: CallbackQuery, session: AsyncSession) -> None:
    gang = await get_gang(session, callback.from_user.id)
    if gang is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        await _render_gang_screen(session, callback.from_user.id, gang.name), reply_markup=gang_menu()
    )


@router.callback_query(F.data == CB_GANG_BACK)
async def cb_gang_back(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    gang = await get_gang(session, callback.from_user.id)
    if gang is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message, await _render_gang_screen(session, callback.from_user.id, gang.name), reply_markup=gang_menu()
    )


@router.callback_query(F.data.startswith(CB_GANG_CAMP_MOVE_PREFIX))
async def cb_gang_camp_move(callback: CallbackQuery, session: AsyncSession) -> None:
    gang = await get_gang(session, callback.from_user.id)
    if gang is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        from_camp, to_camp, percent_raw = callback.data.removeprefix(CB_GANG_CAMP_MOVE_PREFIX).split(":")
        moved = await move_between_camps(session, callback.from_user.id, from_camp, to_camp, int(percent_raw))
    except (InvalidCampMoveError, ValueError):
        await callback.answer()
        return

    # Popup — без HTML.
    await callback.answer(
        CAMP_MOVED.format(moved=format_number(moved)) if moved else CAMP_NOTHING_TO_MOVE, show_alert=not moved
    )
    if moved:
        await safe_edit_text(
            callback.message,
            await _render_gang_screen(session, callback.from_user.id, gang.name),
            reply_markup=gang_menu(),
        )


# --- ручная сборка лагерей по отрядам ---


def _other_camp(camp: str) -> str:
    return CAMP_DEFENSE if camp == CAMP_ATTACK else CAMP_ATTACK


def _parse_squad(raw: str) -> tuple[str, int, int, str, int]:
    """`{rank}:{stars}:{level}:{school}:{school_level}` → кортеж; ValueError на мусоре."""
    rank, stars, level, school, school_level = raw.split(":")
    return rank, int(stars), int(level), school, int(school_level)


def _render_squads(squads: list[Squad], page: int) -> tuple[str, InlineKeyboardMarkup]:
    if not squads:
        return SQUADS_EMPTY, squads_menu([], 0)
    # Сводка по лагерям — из тех же отрядов, без второго запроса к стопкам.
    text = SQUADS_HEADER.format(
        attack_quantity=format_number(sum(sq.attack for sq in squads)),
        attack_power=format_number(sum(sq.attack * sq.unit_power for sq in squads)),
        defense_quantity=format_number(sum(sq.defense for sq in squads)),
        defense_power=format_number(sum(sq.defense * sq.unit_power for sq in squads)),
    )
    buttons = [
        (
            squad_key(sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level),
            SQUAD_BTN.format(
                title=squad_title(sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level),
                attack=format_number(sq.attack),
                defense=format_number(sq.defense),
            ),
        )
        for sq in squads
    ]
    return text, squads_menu(buttons, page)


def _render_squad(squad: Squad) -> str:
    return SQUAD_SCREEN.format(
        title=squad_title(squad.rank, squad.stars, squad.training_level, squad.school, squad.school_level),
        unit_power=format_number(squad.unit_power),
        attack=format_number(squad.attack),
        defense=format_number(squad.defense),
    )


@router.callback_query(F.data.startswith(CB_GANG_SQUADS_PREFIX))
async def cb_gang_squads(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    try:
        page = int(callback.data.removeprefix(CB_GANG_SQUADS_PREFIX))
    except ValueError:
        page = 0
    await callback.answer()
    text, markup = _render_squads(await list_squads(session, callback.from_user.id), page)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_GANG_SQUAD_PREFIX))
async def cb_gang_squad(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    # Сюда же ведёт «◀️ К отряду» из промпта своего числа — FSM чистим всегда.
    await state.clear()
    try:
        rank, stars, level, school, slevel = _parse_squad(callback.data.removeprefix(CB_GANG_SQUAD_PREFIX))
    except ValueError:
        await callback.answer()
        return
    squad = await get_squad(session, callback.from_user.id, rank, stars, level, school, slevel)
    if squad is None:
        await callback.answer(SQUAD_GONE, show_alert=True)
        text, markup = _render_squads(await list_squads(session, callback.from_user.id), 0)
        await safe_edit_text(callback.message, text, reply_markup=markup)
        return
    await callback.answer()
    await safe_edit_text(callback.message, _render_squad(squad), reply_markup=squad_menu(rank, stars, level, school, slevel))


@router.callback_query(F.data.startswith(CB_GANG_SQUAD_MOVE_PREFIX))
async def cb_gang_squad_move(callback: CallbackQuery, session: AsyncSession) -> None:
    user_id = callback.from_user.id
    try:
        raw_squad, from_camp, amount_raw = callback.data.removeprefix(CB_GANG_SQUAD_MOVE_PREFIX).rsplit(":", 2)
        rank, stars, level, school, slevel = _parse_squad(raw_squad)
        if amount_raw == AMOUNT_HALF:
            share = {"percent": 50}
        elif amount_raw == AMOUNT_ALL:
            share = {"percent": 100}
        else:
            share = {"amount": int(amount_raw)}
        moved = await move_squad(
            session, user_id, rank=rank, stars=stars, training_level=level, school=school, school_level=slevel,
            from_camp=from_camp, to_camp=_other_camp(from_camp), **share,
        )
    except (InvalidCampMoveError, ValueError):
        await callback.answer()
        return

    if not moved:
        await callback.answer(SQUAD_NOTHING_TO_MOVE, show_alert=True)
        return
    await callback.answer(CAMP_MOVED.format(moved=format_number(moved)))  # popup — без HTML
    squad = await get_squad(session, user_id, rank, stars, level, school, slevel)
    if squad is not None:
        await safe_edit_text(callback.message, _render_squad(squad), reply_markup=squad_menu(rank, stars, level, school, slevel))


@router.callback_query(F.data.startswith(CB_GANG_SQUAD_CUSTOM_PREFIX))
async def cb_gang_squad_custom(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    try:
        raw_squad, from_camp = callback.data.removeprefix(CB_GANG_SQUAD_CUSTOM_PREFIX).rsplit(":", 1)
        rank, stars, level, school, slevel = _parse_squad(raw_squad)
        if from_camp not in CAMPS:
            raise ValueError(from_camp)
    except ValueError:
        await callback.answer()
        return
    squad = await get_squad(session, callback.from_user.id, rank, stars, level, school, slevel)
    if squad is None:
        await callback.answer(SQUAD_GONE, show_alert=True)
        return

    await state.set_state(GangStates.waiting_squad_amount)
    await state.update_data(rank=rank, stars=stars, level=level, school=school, slevel=slevel, from_camp=from_camp)
    await callback.answer()
    await safe_edit_text(
        callback.message,
        SQUAD_AMOUNT_PROMPT.format(
            title=squad_title(rank, stars, level, school, slevel),
            direction=DIRECTION_TO_DEFENSE if from_camp == CAMP_ATTACK else DIRECTION_TO_ATTACK,
            available=format_number(squad.attack if from_camp == CAMP_ATTACK else squad.defense),
        ),
        reply_markup=squad_back_menu(rank, stars, level, school, slevel),
    )


def _parse_amount(text: str) -> int | None:
    # Большие армии — большие числа: принимаем «1 000 000», «1,000,000», «1_000_000».
    cleaned = "".join(ch for ch in text if ch not in "  ,_")
    if not cleaned.isdigit():
        return None
    value = int(cleaned)
    return value if value > 0 else None


@router.message(GangStates.waiting_squad_amount)
async def on_squad_amount(message: Message, state: FSMContext, session: AsyncSession) -> None:
    amount = _parse_amount(message.text or "")
    if amount is None:
        await message.answer(SQUAD_AMOUNT_INVALID)
        return

    data = await state.get_data()
    await state.clear()
    rank, stars, level, from_camp = data["rank"], data["stars"], data["level"], data["from_camp"]
    school, slevel = data.get("school", ""), data.get("slevel", 0)
    user_id = message.from_user.id
    moved = await move_squad(
        session, user_id, rank=rank, stars=stars, training_level=level, school=school, school_level=slevel,
        from_camp=from_camp, to_camp=_other_camp(from_camp), amount=amount,
    )
    await message.answer(
        SQUAD_MOVED_MESSAGE.format(moved=format_number(moved)) if moved else SQUAD_NOTHING_MOVED_MESSAGE
    )
    squad = await get_squad(session, user_id, rank, stars, level, school, slevel)
    if squad is not None:
        await message.answer(_render_squad(squad), reply_markup=squad_menu(rank, stars, level, school, slevel))
    else:
        text, markup = _render_squads(await list_squads(session, user_id), 0)
        await message.answer(text, reply_markup=markup)


# --- удаление банды (полный сброс) ---


@router.callback_query(F.data == CB_GANG_DELETE_ASK)
async def cb_gang_delete_ask(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    seconds = await request_delete(redis, callback.from_user.id)
    await callback.answer()
    await callback.message.answer(DELETE_CONFIRM_SCREEN.format(seconds=seconds), reply_markup=delete_confirm_menu())


@router.callback_query(F.data == CB_GANG_DELETE_CONFIRM)
async def cb_gang_delete_confirm(callback: CallbackQuery, session: AsyncSession, redis: Redis, state: FSMContext) -> None:
    try:
        await confirm_delete(session, redis, callback.from_user.id)
    except ConfirmExpiredError:
        # Popup — без HTML.
        await callback.answer(DELETE_EXPIRED, show_alert=True)
        return
    await state.clear()
    await callback.answer()
    await safe_clear_markup(callback.message)
    # Заново онбординг — тот же первый экран, что у /start нового игрока.
    await callback.message.answer(DELETE_DONE)
    await callback.message.answer(CHOOSE_COUNTRY, reply_markup=country_menu())
