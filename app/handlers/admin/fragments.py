"""Выдача фрагментов и очков (мастерство, путь, УИ, алхимия)."""
import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.admin_service import admin_service
from app.utils.keyboards.common import back_kb
from app.handlers.admin._common import is_admin, AdminFSM, _show_user_card

router = Router()


@router.callback_query(F.data.startswith("adm_mastery:"))
async def cb_adm_mastery(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await state.set_state(AdminFSM.waiting_mastery_points)
    await state.update_data(target_tg_id=tg_id)
    try:
        await cb.message.edit_text(
            "⭐ Введите количество очков мастерства:",
            reply_markup=back_kb(f"adm_resources:{tg_id}"),
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_mastery_points)
async def msg_adm_mastery(message: Message, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    data = await state.get_data()
    tg_id = data.get("target_tg_id")
    await state.clear()
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число")
        return
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await message.answer("Игрок не найден")
        return
    await admin_service.give_mastery_points(session, found, amount)
    await message.answer(
        f"✅ Выдано {amount} очков мастерства игроку {html.escape(found.full_name)}",
        parse_mode="HTML",
    )
    await _show_user_card(message, session, found)


@router.callback_query(F.data.startswith("adm_pathpts:"))
async def cb_adm_pathpts(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await state.set_state(AdminFSM.waiting_path_points)
    await state.update_data(target_tg_id=tg_id)
    try:
        await cb.message.edit_text(
            "🔷 Введите количество очков пути:",
            reply_markup=back_kb(f"adm_resources:{tg_id}"),
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_path_points)
async def msg_adm_pathpts(message: Message, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    data = await state.get_data()
    tg_id = data.get("target_tg_id")
    await state.clear()
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число")
        return
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await message.answer("Игрок не найден")
        return
    await admin_service.give_path_points(session, found, amount)
    await message.answer(
        f"✅ Выдано {amount} очков пути игроку {html.escape(found.full_name)}",
        parse_mode="HTML",
    )
    await _show_user_card(message, session, found)


@router.callback_query(F.data.startswith("adm_uifrag:"))
async def cb_adm_uifrag(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await state.set_state(AdminFSM.waiting_ui_fragments)
    await state.update_data(target_tg_id=tg_id)
    try:
        await cb.message.edit_text(
            "🔮 Введите количество фрагментов УИ:",
            reply_markup=back_kb(f"adm_resources:{tg_id}"),
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_ui_fragments)
async def msg_adm_uifrag(message: Message, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    data = await state.get_data()
    tg_id = data.get("target_tg_id")
    await state.clear()
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число")
        return
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await message.answer("Игрок не найден")
        return
    await admin_service.give_ui_fragments(session, found, amount)
    await message.answer(
        f"✅ Выдано {amount} фрагментов УИ игроку {html.escape(found.full_name)}",
        parse_mode="HTML",
    )
    await _show_user_card(message, session, found)


@router.callback_query(F.data.startswith("adm_alchfrag:"))
async def cb_adm_alchfrag(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await state.set_state(AdminFSM.waiting_alchemy_fragments)
    await state.update_data(target_tg_id=tg_id)
    try:
        await cb.message.edit_text(
            "🧪 Введите количество фрагментов алхимии:",
            reply_markup=back_kb(f"adm_resources:{tg_id}"),
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_alchemy_fragments)
async def msg_adm_alchfrag(message: Message, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    data = await state.get_data()
    tg_id = data.get("target_tg_id")
    await state.clear()
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число")
        return
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await message.answer("Игрок не найден")
        return
    await admin_service.give_alchemy_fragments(session, found, amount)
    await message.answer(
        f"✅ Выдано {amount} фрагментов алхимии игроку {html.escape(found.full_name)}",
        parse_mode="HTML",
    )
    await _show_user_card(message, session, found)


@router.callback_query(F.data.startswith("adm_pathfrag:"))
async def cb_adm_pathfrag(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await state.set_state(AdminFSM.waiting_path_fragments)
    await state.update_data(target_tg_id=tg_id)
    try:
        await cb.message.edit_text(
            "🔷 Введите количество фрагментов Пути:",
            reply_markup=back_kb(f"adm_resources:{tg_id}"),
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_path_fragments)
async def msg_adm_pathfrag(message: Message, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    data = await state.get_data()
    tg_id = data.get("target_tg_id")
    await state.clear()
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число")
        return
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await message.answer("Игрок не найден")
        return
    await admin_service.give_path_fragments(session, found, amount)
    await message.answer(
        f"✅ Выдано {amount} фрагментов Пути игроку {html.escape(found.full_name)}",
        parse_mode="HTML",
    )
    await _show_user_card(message, session, found)
