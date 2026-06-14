"""Меню раздела ресурсов (входная точка → fragments.py и give_items.py)."""
import html
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.models.user import User
from app.services.admin_service import admin_service
from app.handlers.admin._common import is_admin, _show_user_card

router = Router()


@router.callback_query(F.data.startswith("adm_resources:"))
async def cb_adm_resources(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⭐ Очки мастерства",     callback_data=f"adm_mastery:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🔷 Очки пути",           callback_data=f"adm_pathpts:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🔮 Фрагменты УИ",        callback_data=f"adm_uifrag:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🧪 Фрагменты алхимии",   callback_data=f"adm_alchfrag:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🔷 Фрагменты Пути",      callback_data=f"adm_pathfrag:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🏭 Фрагменты бизнеса",   callback_data=f"adm_bizfrag:{tg_id}"))
    builder.row(InlineKeyboardButton(text="⚔️ Очки войны",          callback_data=f"adm_warpts:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🎯 Очки активности (ОА)", callback_data=f"adm_actpts:{tg_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад",               callback_data=f"adm_user:{tg_id}"))
    try:
        await cb.message.edit_text("📦 Выберите ресурс для выдачи:", reply_markup=builder.as_markup())
    except Exception:
        pass


# ── Гений медицины донат (включение/выключение) ──────────────────────────────

@router.callback_query(F.data.startswith("adm_mg_donat_on:"))
async def cb_adm_mg_donat_on(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    found.med_genius_donat = True
    found.med_genius_level = 5  # донат включает все уровни
    await session.commit()
    await cb.answer(f"✅ МГ-донат включён для {html.escape(found.full_name)}", show_alert=True)
    await _show_user_card(cb.message, session, found)


@router.callback_query(F.data.startswith("adm_mg_donat_off:"))
async def cb_adm_mg_donat_off(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    found.med_genius_donat = False
    await session.commit()
    await cb.answer(f"❌ МГ-донат выключен для {html.escape(found.full_name)}", show_alert=True)
    await _show_user_card(cb.message, session, found)


# ── VVIP — индивидуальная выдача (без клана) ─────────────────────────────────

@router.callback_query(F.data.startswith("adm_user_vvip_on:"))
async def cb_adm_user_vvip_on(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    current = getattr(found, "clan_vvip_level", 0)
    found.clan_vvip_level = current + 1
    await session.commit()
    await cb.answer(
        f"✅ VVIP уровень {found.clan_vvip_level} выдан {html.escape(found.full_name)}",
        show_alert=True,
    )
    await _show_user_card(cb.message, session, found)


@router.callback_query(F.data.startswith("adm_user_vvip_off:"))
async def cb_adm_user_vvip_off(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    found.clan_vvip_level = 0
    await session.commit()
    await cb.answer(
        f"👑 VVIP сброшен для {html.escape(found.full_name)}", show_alert=True
    )
    await _show_user_card(cb.message, session, found)
