import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.services.admin_service import admin_service
from app.utils.keyboards.common import back_kb
from app.handlers.admin._common import is_admin, AdminFSM

router = Router()


@router.callback_query(F.data == "admin_patch")
async def cb_admin_patch(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔧 Сброс прогресса + версия",
        callback_data="admin_patch_reset"
    ))
    builder.row(InlineKeyboardButton(
        text="🔖 Только сменить версию",
        callback_data="admin_version_only"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main"))
    try:
        await cb.message.edit_text(
            "🔧 <b>Патч</b>\n\nВыбери действие:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_patch_reset")
async def cb_admin_patch_reset(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_patch_version)
    try:
        await cb.message.edit_text(
            "🔧 <b>Патч — сброс прогресса</b>\n\n"
            "Введите версию патча в формате <code>1.0.1</code>\n\n"
            "⚠️ Донаты и пробуждения сохранятся.\n"
            "Весь прогресс игроков будет сброшен!",
            reply_markup=back_kb("admin_patch"),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_version_only")
async def cb_admin_version_only(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_version_only)
    try:
        await cb.message.edit_text(
            "🔖 Введите новую версию в формате <code>1.0.1</code>:",
            reply_markup=back_kb("admin_patch"),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_version_only)
async def msg_version_only(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    import re
    version = message.text.strip()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        await message.answer("❌ Неверный формат. Введите версию как <code>1.0.1</code>", parse_mode="HTML")
        return
    await state.clear()
    from app.models.game_version import GameVersion
    gv = GameVersion(version=version, patch_notes=f"Версия {version}")
    session.add(gv)
    await session.flush()
    await message.answer(
        f"✅ Версия обновлена до <b>{version}</b>",
        reply_markup=back_kb("admin_main"),
        parse_mode="HTML",
    )


@router.message(AdminFSM.waiting_patch_version)
async def msg_patch_version(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    import re
    version = message.text.strip()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        await message.answer("❌ Неверный формат. Введите версию как <code>1.0.1</code>", parse_mode="HTML")
        return
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"✅ Подтвердить патч {version}",
        callback_data=f"admin_patch_confirm:{version}"
    ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_main"))
    await message.answer(
        f"⚠️ <b>Подтвердить патч {version}?</b>\n\n"
        f"Прогресс ВСЕХ игроков будет сброшен!\n"
        f"Донаты и пробуждения сохранятся.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("admin_patch_confirm:"))
async def cb_admin_patch_confirm(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    version = cb.data.split(":", 1)[1]

    await cb.answer("⏳ Применяю патч...")

    import asyncio
    from app.models.user import User as UserModel
    from app.models.clan import Clan, ClanMember
    from app.config.game_balance import (
        PATCH_TOP_PLAYER_REWARDS, PATCH_TOP_CLAN_REWARDS,
        PATCH_TOP_PLAYERS_COUNT, PATCH_TOP_CLANS_COUNT,
    )

    # Собираем все данные ДО сброса и ДО закрытия сессии
    top_r = await session.execute(
        select(UserModel.tg_id, UserModel.combat_power)
        .order_by(UserModel.combat_power.desc())
        .limit(PATCH_TOP_PLAYERS_COUNT)
    )
    top_player_tg_ids = [row[0] for row in top_r.all()]

    top_clans_r = await session.execute(
        select(Clan).order_by(Clan.combat_power.desc()).limit(PATCH_TOP_CLANS_COUNT)
    )
    top_clans = top_clans_r.scalars().all()

    # Загружаем tg_id участников топ-кланов одним запросом на клан
    clan_broadcast: list[tuple[int, str, int, list[int]]] = []
    for i, clan in enumerate(top_clans):
        tickets = PATCH_TOP_CLAN_REWARDS.get(i, 3)
        member_tg_r = await session.execute(
            select(UserModel.tg_id)
            .join(ClanMember, ClanMember.user_id == UserModel.id)
            .where(ClanMember.clan_id == clan.id)
        )
        clan_broadcast.append((i + 1, clan.name, tickets, [r[0] for r in member_tg_r.all()]))

    # Список tg_id для общей рассылки
    broadcast_r = await session.execute(
        select(UserModel.tg_id).where(UserModel.notifications_enabled == True)
    )
    broadcast_tg_ids: list[int] = [r[0] for r in broadcast_r.all()]

    count = await admin_service.patch_reset_progress(session, version)
    bot = cb.bot

    # Сразу показываем результат — не ждём рассылки
    try:
        await cb.message.edit_text(
            f"✅ <b>Патч {version} применён!</b>\n\n"
            f"Сброшено: {count} игроков\n"
            f"🏆 Топ-{PATCH_TOP_PLAYERS_COUNT} игроков получат тикеты\n"
            f"🏯 Топ-{PATCH_TOP_CLANS_COUNT} кланов получат тикеты, казны обнулены\n"
            f"📨 Рассылка идёт в фоне...",
            reply_markup=back_kb("admin_main"),
            parse_mode="HTML",
        )
    except Exception:
        pass

    # Вся рассылка в фоне, чтобы не блокировать обработчик
    asyncio.create_task(_broadcast_patch(
        bot, version,
        broadcast_tg_ids, top_player_tg_ids, PATCH_TOP_PLAYER_REWARDS,
        clan_broadcast,
    ))


async def _broadcast_patch(
    bot,
    version: str,
    broadcast_tg_ids: list[int],
    top_player_tg_ids: list[int],
    top_rewards: dict,
    clan_broadcast: list[tuple[int, str, int, list[int]]],
) -> None:
    import asyncio

    patch_text = (
        f"🔧 <b>Патч {version} применён!</b>\n\n"
        f"Прогресс всех игроков сброшен.\n"
        f"Донаты и пробуждения сохранены.\n\n"
        f"Удачи в новом старте! 💪"
    )
    for tg_id in broadcast_tg_ids:
        try:
            await bot.send_message(tg_id, patch_text, parse_mode="HTML")
        except Exception:
            pass
        await asyncio.sleep(0.05)  # ~20 msg/sec, не превышаем лимит Telegram

    for i, tg_id in enumerate(top_player_tg_ids):
        tickets = top_rewards.get(i, 3)
        try:
            await bot.send_message(
                tg_id,
                f"🏆 <b>Награда за топ-{i+1} перед патчем!</b>\n\n"
                f"Вы заняли <b>#{i+1} место</b> по боевой мощи.\n"
                f"🎟 Получено: <b>+{tickets} тикетов</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass

    for place, clan_name, tickets, member_tg_ids in clan_broadcast:
        for tg_id in member_tg_ids:
            try:
                await bot.send_message(
                    tg_id,
                    f"🏯 <b>Награда клану {html.escape(clan_name)} за топ-{place}!</b>\n\n"
                    f"Ваш клан занял <b>#{place} место</b> по боевой мощи.\n"
                    f"🎟 Получено: <b>+{tickets} тикетов</b>\n"
                    f"🏦 Казна клана обнулена.",
                    parse_mode="HTML",
                )
            except Exception:
                pass


@router.callback_query(F.data == "admin_backup")
async def cb_admin_backup(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    backups = await admin_service.list_backups()
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💾 Создать новый бэкап", callback_data="admin_backup_create"
    ))
    if backups:
        builder.row(InlineKeyboardButton(text="─── Восстановить из ───", callback_data="noop"))
        for b in backups[:8]:
            builder.row(InlineKeyboardButton(
                text=f"📁 {b['name']} ({b['size_kb']} KB)",
                callback_data=f"admin_restore:{b['name']}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main"))
    backup_list = "\n".join(
        f"  📁 {b['name']} — {b['size_kb']} KB" for b in backups[:8]
    ) if backups else "  Бэкапов нет"
    try:
        await cb.message.edit_text(
            f"💾 <b>Бэкапы</b>\n\nСписок бэкапов:\n{backup_list}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_backup_create")
async def cb_admin_backup_create(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    await cb.answer("⏳ Создаю бэкап...")
    result = await admin_service.create_backup()
    if result["ok"]:
        try:
            await cb.message.edit_text(
                f"✅ <b>Бэкап создан!</b>\n\n"
                f"Файл: <code>{result['filename']}</code>\n"
                f"Размер: {result['size_kb']} KB",
                reply_markup=back_kb("admin_backup"),
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        try:
            await cb.message.edit_text(
                "❌ Ошибка создания бэкапа",
                reply_markup=back_kb("admin_backup"),
                parse_mode="HTML",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("admin_restore:"))
async def cb_admin_restore(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    filename = cb.data.split(":", 1)[1]
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="⚠️ Подтвердить восстановление",
        callback_data=f"admin_restore_confirm:{filename}"
    ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_backup"))
    try:
        await cb.message.edit_text(
            f"⚠️ <b>Восстановление из бэкапа</b>\n\n"
            f"Файл: <code>{filename}</code>\n\n"
            f"❗ Текущие данные будут перезаписаны!\nПодтвердить?",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("admin_restore_confirm:"))
async def cb_admin_restore_confirm(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    filename = cb.data.split(":", 1)[1]
    filepath = f"/app/backups/{filename}"
    await cb.answer("⏳ Восстанавливаю...")
    result = await admin_service.restore_backup(filepath)
    try:
        if result["ok"]:
            await cb.message.edit_text(
                f"✅ <b>Восстановлено из {filename}</b>",
                reply_markup=back_kb("admin_main"),
                parse_mode="HTML",
            )
        else:
            await cb.message.edit_text(
                f"❌ Ошибка восстановления\n{result.get('reason', '')}",
                reply_markup=back_kb("admin_backup"),
                parse_mode="HTML",
            )
    except Exception:
        pass
