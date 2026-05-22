import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.admin_service import admin_service
from app.utils.keyboards.admin import admin_user_kb
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num, fmt_power, phase_label
from app.handlers.admin._common import is_admin, AdminFSM, _show_user_card

router = Router()


@router.callback_query(F.data == "admin_find")
async def cb_admin_find(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_search)
    try:
        await cb.message.edit_text(
            "🔍 Введите tg_id, @username или название банды:",
            reply_markup=back_kb("admin_main"),
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_search)
async def msg_admin_search(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    await state.clear()
    query = message.text.strip()
    found = await admin_service.find_user(session, query)
    if not found:
        await message.answer("❌ Игрок не найден", reply_markup=back_kb("admin_main"))
        return

    from app.repositories.title_repo import title_repo
    titles_str = await title_repo.get_titles_display(session, found.id)

    await message.answer(
        f"👤 <b>{html.escape(found.full_name)}</b>\n"
        f"🆔 tg_id: <code>{found.tg_id}</code>\n"
        f"🏴 Банда: {html.escape(found.gang_name) if found.gang_name else '—'}\n"
        f"{phase_label(found.phase)}\n"
        f"⚔️ Мощь: {fmt_power(found.combat_power)}\n"
        f"💰 Монеты: {fmt_num(found.nh_coins)}\n"
        f"🎟 Тикеты: {found.tickets}/{found.max_tickets}\n"
        f"🌟 Пробуждений: {found.prestige_level}\n"
        f"💎 Титулы:\n{titles_str}",
        reply_markup=admin_user_kb(found.tg_id),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_user:"))
async def cb_adm_user(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    await _show_user_card(cb.message, session, found)


@router.callback_query(F.data.startswith("adm_coins:"))
async def cb_adm_coins(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await state.set_state(AdminFSM.waiting_coins)
    await state.update_data(target_tg_id=tg_id)
    try:
        await cb.message.edit_text(
            f"💰 Введите количество монет для игрока {tg_id}:",
            reply_markup=back_kb(f"adm_user:{tg_id}"),
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_coins)
async def msg_adm_coins(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
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
    await admin_service.give_coins(session, found, amount)
    await message.answer(
        f"✅ Выдано {fmt_num(amount)} монет игроку {html.escape(found.full_name)}",
        parse_mode="HTML",
    )
    await _show_user_card(message, session, found)


@router.callback_query(F.data.startswith("adm_tickets:"))
async def cb_adm_tickets(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await state.set_state(AdminFSM.waiting_tickets)
    await state.update_data(target_tg_id=tg_id)
    try:
        await cb.message.edit_text(
            f"🎟 Введите количество тикетов:",
            reply_markup=back_kb(f"adm_user:{tg_id}"),
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_tickets)
async def msg_adm_tickets(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    data = await state.get_data()
    tg_id = data.get("target_tg_id")
    await state.clear()
    try:
        count = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число")
        return
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await message.answer("Игрок не найден")
        return
    await admin_service.give_tickets(session, found, count)
    await message.answer(
        f"✅ Выдано {count} тикетов игроку {html.escape(found.full_name)}",
        parse_mode="HTML",
    )
    await _show_user_card(message, session, found)


@router.callback_query(F.data.startswith("adm_prestige:"))
async def cb_adm_prestige(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    old = found.prestige_level
    await admin_service.give_prestige(session, found)
    await cb.answer(
        f"✅ Пробуждение {found.full_name}: {old} → {found.prestige_level} ⭐",
        show_alert=True,
    )
    try:
        if found.notifications_enabled:
            await cb.bot.send_message(
                found.tg_id,
                f"⭐ <b>Вам добавлено пробуждение!</b>\n\n"
                f"Уровень: {found.prestige_level}/10",
                parse_mode="HTML",
            )
    except Exception:
        pass
    await _show_user_card(cb.message, session, found)


@router.callback_query(F.data.startswith("adm_unprestige:"))
async def cb_adm_unprestige(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    old = found.prestige_level
    await admin_service.remove_prestige(session, found)
    await cb.answer(
        f"✅ Пробуждение {found.full_name}: {old} → {found.prestige_level} ⭐",
        show_alert=True,
    )
    await _show_user_card(cb.message, session, found)


@router.callback_query(F.data.startswith("adm_delete_confirm:"))
async def cb_adm_delete_confirm(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💀 Да, удалить насовсем", callback_data=f"adm_delete_do:{tg_id}"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"adm_user:{tg_id}"))
    try:
        await cb.message.edit_text(
            f"⚠️ <b>Удаление аккаунта {tg_id}</b>\n\nВсе данные игрока будут удалены без возможности восстановления!\n\nПодтвердить?",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_delete_do:"))
async def cb_adm_delete_do(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    name = found.full_name
    await admin_service.delete_user(session, found)
    await cb.answer(f"💀 Аккаунт {name} удалён!")
    try:
        await cb.message.edit_text(
            f"💀 <b>Аккаунт удалён</b>\n\n{html.escape(name)} (tg_id: {tg_id})",
            reply_markup=back_kb("admin_main"),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_clear_buildings:"))
async def cb_adm_clear_buildings(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    from sqlalchemy import delete
    from app.models.building import UserBuilding
    result = await session.execute(
        delete(UserBuilding).where(UserBuilding.user_id == found.id)
    )
    from app.services.business_service import business_service
    found.income_per_minute = 0
    await session.flush()
    await business_service._recalc_income(session, found)
    deleted = result.rowcount
    await cb.answer(f"🏗 Удалено {deleted} зданий, доход пересчитан", show_alert=True)
