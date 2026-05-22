import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sa_select
from app.models.user import User
from app.utils.keyboards.common import back_kb
from app.handlers.admin._common import is_admin, AdminFSM, _show_clan_donat_panel

router = Router()


@router.callback_query(F.data == "admin_clan_donat")
async def cb_admin_clan_donat(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_clan_donat_search)
    try:
        await cb.message.edit_text(
            "🏯 <b>Клан-донат</b>\n\nВведите название клана:",
            reply_markup=back_kb("admin_main"),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_clan_donat_search)
async def msg_clan_donat_search(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    await state.clear()
    from app.models.clan import Clan
    name = message.text.strip()
    clan = await session.scalar(sa_select(Clan).where(Clan.name == name))
    if not clan:
        result = await session.execute(
            sa_select(Clan).where(Clan.name.ilike(f"%{name}%")).limit(10)
        )
        clans = result.scalars().all()
        if not clans:
            await message.answer("❌ Клан не найден", reply_markup=back_kb("admin_main"))
            return
        if len(clans) == 1:
            clan = clans[0]
        else:
            builder = InlineKeyboardBuilder()
            for c in clans:
                builder.row(InlineKeyboardButton(
                    text=c.name,
                    callback_data=f"adm_clan_donat_view:{c.id}"
                ))
            builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main"))
            await message.answer(
                "🔍 Найдено несколько кланов:",
                reply_markup=builder.as_markup(),
            )
            return
    await _show_clan_donat_panel(message, clan)


@router.callback_query(F.data.startswith("adm_clan_donat_view:"))
async def cb_adm_clan_donat_view(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    clan_id = int(cb.data.split(":")[1])
    from app.models.clan import Clan
    clan = await session.scalar(sa_select(Clan).where(Clan.id == clan_id))
    if not clan:
        await cb.answer("Клан не найден", show_alert=True)
        return
    await _show_clan_donat_panel(cb.message, clan)


@router.callback_query(F.data.startswith("adm_clan_donat_apply:"))
async def cb_adm_clan_donat_apply(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    clan_id, package_id = int(parts[1]), parts[2]
    from app.models.clan import Clan, ClanMember
    from app.services.clan import clan_service
    from app.models.user import User as UserModel
    clan = await session.scalar(sa_select(Clan).where(Clan.id == clan_id))
    if not clan:
        await cb.answer("Клан не найден", show_alert=True)
        return
    result = await clan_service.apply_clan_donat(session, clan, package_id)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return
    pkg = result["package"]
    await cb.answer(f"✅ {pkg.name} выдан клану {clan.name}!")
    await session.refresh(clan)
    await _show_clan_donat_panel(cb.message, clan)

    # Уведомляем всех участников клана
    from app.bot_instance import get_bot
    bot = get_bot()
    if bot:
        bonus_parts = []
        if pkg.income_pct: bonus_parts.append(f"💰 Доход +{pkg.income_pct}%")
        if pkg.ticket_pct: bonus_parts.append(f"🎟 Шанс тикета +{pkg.ticket_pct}%")
        if pkg.train_pct:  bonus_parts.append(f"🏋 Тренировка +{pkg.train_pct}%")
        bonus_str = "\n".join(bonus_parts)

        total_parts = []
        if clan.donat_income_pct: total_parts.append(f"💰 Доход +{clan.donat_income_pct}%")
        if clan.donat_ticket_pct: total_parts.append(f"🎟 Тикет +{clan.donat_ticket_pct}%")
        if clan.donat_train_pct:  total_parts.append(f"🏋 Трен. +{clan.donat_train_pct}%")
        total_str = " | ".join(total_parts)

        import html as _html
        text = (
            f"💎 <b>Клан получил донат!</b>\n\n"
            f"🏯 {_html.escape(clan.name)}\n"
            f"📦 Пакет: <b>{pkg.name}</b>\n\n"
            f"{bonus_str}\n\n"
            f"📊 Итого донат-бонусов клана:\n{total_str}"
        )

        members_r = await session.execute(
            sa_select(ClanMember).where(ClanMember.clan_id == clan.id)
        )
        user_ids = [m.user_id for m in members_r.scalars().all()]
        users_r = await session.execute(
            sa_select(UserModel).where(UserModel.id.in_(user_ids))
        )
        for u in users_r.scalars().all():
            try:
                await bot.send_message(u.tg_id, text, parse_mode="HTML")
            except Exception:
                pass


@router.callback_query(F.data.startswith("adm_clan_vvip_level:"))
async def cb_adm_clan_vvip_level(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    clan_id = int(cb.data.split(":")[1])
    from app.models.clan import Clan, ClanMember
    from app.services.clan import clan_service
    from app.models.user import User as UserModel
    from app.services.clan.donat import VVIP_MAX_LEVEL
    clan = await session.scalar(sa_select(Clan).where(Clan.id == clan_id))
    if not clan:
        await cb.answer("Клан не найден", show_alert=True)
        return
    result = await clan_service.apply_full_level(session, clan)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return
    lvl = result["level"]
    await cb.answer(f"✅ VVIP уровень {lvl} выдан клану {clan.name}!")
    await session.refresh(clan)
    await _show_clan_donat_panel(cb.message, clan)

    from app.bot_instance import get_bot
    bot = get_bot()
    if bot:
        import html as _html
        text = (
            f"👑 <b>Клан получил VVIP уровень {lvl}/{VVIP_MAX_LEVEL}!</b>\n\n"
            f"🏯 {_html.escape(clan.name)}\n\n"
            f"💰 Доход +{clan.donat_income_pct}%\n"
            f"🍀 Тикет +{clan.donat_ticket_pct}%\n"
            f"🏋 Тренировка +{clan.donat_train_pct}%"
        )
        members_r = await session.execute(
            sa_select(ClanMember).where(ClanMember.clan_id == clan.id)
        )
        user_ids = [m.user_id for m in members_r.scalars().all()]
        users_r = await session.execute(
            sa_select(UserModel).where(UserModel.id.in_(user_ids))
        )
        for u in users_r.scalars().all():
            try:
                await bot.send_message(u.tg_id, text, parse_mode="HTML")
            except Exception:
                pass


@router.callback_query(F.data.startswith("adm_clan_donat_reset:"))
async def cb_adm_clan_donat_reset(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    clan_id = int(cb.data.split(":")[1])
    from app.models.clan import Clan
    from app.services.clan import clan_service
    clan = await session.scalar(sa_select(Clan).where(Clan.id == clan_id))
    if not clan:
        await cb.answer("Клан не найден", show_alert=True)
        return
    await clan_service.reset_clan_donat(session, clan)
    await cb.answer("✅ Донат-бонусы клана сброшены!")
    await session.refresh(clan)
    await _show_clan_donat_panel(cb.message, clan)


@router.message(Command("unban"))
async def cmd_unban(message: Message, user: User):
    if not is_admin(user.tg_id):
        return
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].lstrip("-").isdigit():
        await message.answer("Использование: /unban <user_id>")
        return
    uid = int(parts[1])
    import redis.asyncio as aioredis
    from app.config import settings as cfg
    r = aioredis.from_url(cfg.redis_url, decode_responses=True)
    await r.delete(f"rl:ban:{uid}", f"rl:vio:{uid}", f"rl:cnt:{uid}")
    await r.aclose()
    await message.answer(f"✅ Пользователь {uid} разбанен и счётчик нарушений сброшен.")


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()
