"""Админка — Районы, города, императоры (хендлеры)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, SECTION_WORLD
from bot.constant.admin import world as C
from bot.db.models.city import City
from bot.db.repositories import district as district_repo
from bot.handlers.admin.common import guard, parse_id
from bot.keyboards.admin import world as K
from bot.services.admin import players as players_svc
from bot.services.admin import roles
from bot.services.admin import world as svc
from bot.states.admin_world import AdminWorldStates
from bot.texts.admin import world as T
from bot.utils.formatting import esc
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_world")


def _owner(row) -> str:
    if row.owner_id is None:
        return T.OWNER_BOTS
    return esc(row.owner_gang or row.owner_name or f"id{row.owner_id}") + f" (id{row.owner_id})"


async def _city_screen(session: AsyncSession, city_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    view = await svc.city_view(session, city_id)
    if view is None:
        return None
    lines = "\n".join(T.DISTRICT_LINE.format(number=r.number, owner=_owner(r)) for r in view.districts)
    text = T.CITY_CARD.format(
        name=esc(view.city.name), country=view.city.country_code, emperor=esc(svc.player_label(view.emperor)),
        total=len(view.districts), bots=sum(1 for r in view.districts if r.owner_id is None),
        challenges=view.pending_challenges, districts=lines,
    )
    return text, K.city_card(city_id, [(r.id, r.number) for r in view.districts], view.emperor is not None)


async def _show_city(callback: CallbackQuery, session: AsyncSession, city_id: int) -> None:
    screen = await _city_screen(session, city_id)
    if screen is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, screen[0], reply_markup=screen[1])


async def _district_screen(session: AsyncSession, district_id: int):
    row = await district_repo.get_row(session, district_id)
    if row is None:
        return None
    city = await session.get(City, row.city_id)
    ch = await svc.district_pending(session, district_id)
    challenge = T.CHALLENGE_YES.format(attacker=ch.attacker_id, defender=ch.defender_id) if ch else T.CHALLENGE_NONE
    text = T.DISTRICT_CARD.format(number=row.number, city=esc(city.name), owner=_owner(row), challenge=challenge)
    return row, text, K.district_card(district_id, row.city_id)


@router.callback_query(F.data == f"{CB_ADMIN_SECTION_PREFIX}{SECTION_WORLD}")
async def cb_section(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    await state.clear()
    await callback.answer()
    await safe_edit_text(callback.message, T.WORLD_MENU, reply_markup=K.menu())


@router.callback_query(F.data == C.CB_W_FIND)
async def cb_find(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    await state.set_state(AdminWorldStates.waiting_city)
    await callback.answer()
    await safe_edit_text(callback.message, T.ASK_CITY, reply_markup=K.back_to_menu_only())


@router.message(StateFilter(AdminWorldStates.waiting_city), F.text)
async def msg_city(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_WORLD):
        return
    cities = await svc.find_cities(session, message.text)
    if not cities:
        await message.answer(T.CITY_NOT_FOUND, reply_markup=K.back_to_menu_only())
        return
    await state.clear()
    if len(cities) == 1:
        screen = await _city_screen(session, cities[0].id)
        await message.answer(screen[0], reply_markup=screen[1])
        return
    await message.answer(T.PICK_CITY, reply_markup=K.pick_cities([(c.id, c.name, c.country_code) for c in cities]))


@router.callback_query(F.data.startswith(C.CB_W_CITY_PREFIX))
async def cb_city(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    city_id = parse_id(callback.data, C.CB_W_CITY_PREFIX)
    if city_id is None:
        return
    await state.clear()
    await _show_city(callback, session, city_id)


@router.callback_query(F.data.startswith(C.CB_W_DISTRICT_PREFIX))
async def cb_district(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    did = parse_id(callback.data, C.CB_W_DISTRICT_PREFIX)
    screen = await _district_screen(session, did) if did is not None else None
    if screen is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await state.clear()
    await callback.answer()
    await safe_edit_text(callback.message, screen[1], reply_markup=screen[2])


# --- владелец района ---

@router.callback_query(F.data.startswith(C.CB_W_SET_OWNER_PREFIX))
async def cb_set_owner(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    did = parse_id(callback.data, C.CB_W_SET_OWNER_PREFIX)
    row = await district_repo.get_row(session, did) if did is not None else None
    if row is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await state.set_state(AdminWorldStates.waiting_owner)
    await state.update_data(district_id=did, city_id=row.city_id, number=row.number)
    await callback.answer()
    await safe_edit_text(callback.message, T.ASK_OWNER.format(number=row.number), reply_markup=K.to_city(row.city_id))


@router.message(StateFilter(AdminWorldStates.waiting_owner), F.text)
async def msg_owner(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_WORLD):
        return
    data = await state.get_data()
    user = await players_svc.find(session, message.text)
    if user is None:
        await message.answer(T.PLAYER_NOT_FOUND, reply_markup=K.to_city(data["city_id"]))
        return
    result = await svc.set_district_owner(session, message.from_user.id, data["district_id"], user)
    await state.clear()
    notes = {"ok": T.DONE_OWNER.format(number=data["number"], owner=esc(svc.player_label(user))), "same": T.ALERT_SAME_OWNER}
    await message.answer(notes.get(result, T.ALERT_STALE), reply_markup=K.to_city(data["city_id"]))


@router.callback_query(F.data.startswith(C.CB_W_RESET_ASK_PREFIX))
async def cb_reset_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    did = parse_id(callback.data, C.CB_W_RESET_ASK_PREFIX)
    row = await district_repo.get_row(session, did) if did is not None else None
    if row is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    if row.owner_id is None:
        await callback.answer(T.ALERT_ALREADY_BOTS, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message, T.CONFIRM_RESET.format(number=row.number, owner=_owner(row)),
        reply_markup=K.confirm(f"{C.CB_W_RESET_OK_PREFIX}{did}", f"{C.CB_W_DISTRICT_PREFIX}{did}"),
    )


@router.callback_query(F.data.startswith(C.CB_W_RESET_OK_PREFIX))
async def cb_reset_ok(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    did = parse_id(callback.data, C.CB_W_RESET_OK_PREFIX)
    row = await district_repo.get_row(session, did) if did is not None else None
    if row is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    result = await svc.reset_district(session, callback.from_user.id, did)
    await callback.answer(T.DONE_RESET.format(number=row.number) if result == "ok" else T.ALERT_ALREADY_BOTS, show_alert=True)
    await _show_city(callback, session, row.city_id)


# --- император ---

@router.callback_query(F.data.startswith(C.CB_W_SET_EMP_PREFIX))
async def cb_set_emp(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    city_id = parse_id(callback.data, C.CB_W_SET_EMP_PREFIX)
    view = await svc.city_view(session, city_id) if city_id is not None else None
    if view is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await state.set_state(AdminWorldStates.waiting_emperor)
    await state.update_data(city_id=city_id, city=view.city.name)
    await callback.answer()
    await safe_edit_text(callback.message, T.ASK_EMPEROR.format(city=esc(view.city.name)), reply_markup=K.to_city(city_id))


@router.message(StateFilter(AdminWorldStates.waiting_emperor), F.text)
async def msg_emperor(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_WORLD):
        return
    data = await state.get_data()
    user = await players_svc.find(session, message.text)
    if user is None:
        await message.answer(T.PLAYER_NOT_FOUND, reply_markup=K.to_city(data["city_id"]))
        return
    ok = await svc.set_emperor(session, message.from_user.id, data["city_id"], user)
    await state.clear()
    note = T.DONE_EMP.format(city=esc(data["city"]), emperor=esc(svc.player_label(user))) if ok else T.ALERT_STALE
    await message.answer(note, reply_markup=K.to_city(data["city_id"]))


@router.callback_query(F.data.startswith(C.CB_W_DEL_EMP_ASK_PREFIX))
async def cb_del_emp_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    city_id = parse_id(callback.data, C.CB_W_DEL_EMP_ASK_PREFIX)
    view = await svc.city_view(session, city_id) if city_id is not None else None
    if view is None or view.emperor is None:
        await callback.answer(T.ALERT_NO_EMPEROR, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message, T.CONFIRM_DEL_EMP.format(city=esc(view.city.name), emperor=esc(svc.player_label(view.emperor))),
        reply_markup=K.confirm(f"{C.CB_W_DEL_EMP_OK_PREFIX}{city_id}", f"{C.CB_W_CITY_PREFIX}{city_id}"),
    )


@router.callback_query(F.data.startswith(C.CB_W_DEL_EMP_OK_PREFIX))
async def cb_del_emp_ok(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    city_id = parse_id(callback.data, C.CB_W_DEL_EMP_OK_PREFIX)
    if city_id is None:
        return
    ok = await svc.remove_emperor(session, callback.from_user.id, city_id)
    await callback.answer(T.DONE_DEL_EMP if ok else T.ALERT_NO_EMPEROR, show_alert=True)
    await _show_city(callback, session, city_id)


# --- вызовы и войны ---

@router.callback_query(F.data.startswith(C.CB_W_CH_ASK_PREFIX))
async def cb_ch_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    city_id = parse_id(callback.data, C.CB_W_CH_ASK_PREFIX)
    view = await svc.city_view(session, city_id) if city_id is not None else None
    if view is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    if not view.pending_challenges:
        await callback.answer(T.ALERT_NOTHING, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message, T.CONFIRM_CANCEL_CH.format(city=esc(view.city.name), count=view.pending_challenges),
        reply_markup=K.confirm(f"{C.CB_W_CH_OK_PREFIX}{city_id}", f"{C.CB_W_CITY_PREFIX}{city_id}"),
    )


@router.callback_query(F.data.startswith(C.CB_W_CH_OK_PREFIX))
async def cb_ch_ok(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    city_id = parse_id(callback.data, C.CB_W_CH_OK_PREFIX)
    if city_id is None:
        return
    count = await svc.cancel_city_challenges(session, callback.from_user.id, city_id)
    await callback.answer(T.DONE_CANCEL_CH.format(count=count), show_alert=True)
    await _show_city(callback, session, city_id)


@router.callback_query(F.data.startswith(C.CB_W_WAR_ASK_PREFIX))
async def cb_war_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    city_id = parse_id(callback.data, C.CB_W_WAR_ASK_PREFIX)
    view = await svc.city_view(session, city_id) if city_id is not None else None
    if view is None or view.emperor is None:
        await callback.answer(T.ALERT_NO_EMPEROR, show_alert=True)
        return
    count = await svc.pending_wars_of(session, view.emperor.id)
    if not count:
        await callback.answer(T.ALERT_NOTHING, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message, T.CONFIRM_CANCEL_WAR.format(emperor=esc(svc.player_label(view.emperor)), count=count),
        reply_markup=K.confirm(f"{C.CB_W_WAR_OK_PREFIX}{city_id}", f"{C.CB_W_CITY_PREFIX}{city_id}"),
    )


@router.callback_query(F.data.startswith(C.CB_W_WAR_OK_PREFIX))
async def cb_war_ok(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_WORLD):
        return
    city_id = parse_id(callback.data, C.CB_W_WAR_OK_PREFIX)
    view = await svc.city_view(session, city_id) if city_id is not None else None
    if view is None or view.emperor is None:
        await callback.answer(T.ALERT_NO_EMPEROR, show_alert=True)
        return
    count = await svc.cancel_emperor_wars(session, callback.from_user.id, view.emperor.id)
    await callback.answer(T.DONE_CANCEL_WAR.format(count=count), show_alert=True)
    await _show_city(callback, session, city_id)
