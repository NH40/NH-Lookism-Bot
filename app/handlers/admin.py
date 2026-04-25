from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.services.admin_service import admin_service
from app.services.title_service import title_service
from app.utils.keyboards.admin import admin_main_kb, admin_user_kb, titles_grant_kb
from app.utils.keyboards.common import back_kb, confirm_kb
from app.utils.formatters import fmt_num, fmt_power, phase_label
from app.config import settings

router = Router()


def is_admin(tg_id: int) -> bool:
    return tg_id in settings.admin_ids_list


class AdminFSM(StatesGroup):
    waiting_search = State()
    waiting_coins = State()
    waiting_tickets = State()
    waiting_patch_version = State()
    waiting_restore_confirm = State()
    waiting_broadcast = State()
    waiting_bulk_coins = State()
    waiting_bulk_tickets = State()


# ── Главное меню ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_main")
async def cb_admin_main(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    try:
        await cb.message.edit_text(
            "🔧 <b>Панель администратора</b>",
            reply_markup=admin_main_kb(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    stats = await admin_service.get_stats(session)
    phase_lines = "\n".join(
        f"  {phase_label(p)}: {c}" for p, c in stats["phases"].items()
    )
    from app.models.game_version import GameVersion
    gv_result = await session.execute(
        select(GameVersion).order_by(GameVersion.applied_at.desc()).limit(1)
    )
    gv = gv_result.scalar_one_or_none()
    version_str = f"Версия: {gv.version}" if gv else "Версия: не задана"

    await cb.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"Всего игроков: {stats['total']}\n"
        f"🔖 {version_str}\n\n"
        f"По фазам:\n{phase_lines}",
        reply_markup=back_kb("admin_main"),
        parse_mode="HTML",
    )


# ── Поиск игрока ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_find")
async def cb_admin_find(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_search)
    await cb.message.edit_text(
        "🔍 Введите tg_id, @username или название банды:",
        reply_markup=back_kb("admin_main"),
    )


@router.message(AdminFSM.waiting_search)
async def msg_admin_search(
    message: Message, session: AsyncSession,
    user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    await state.clear()
    query = message.text.strip()
    found = await admin_service.find_user(session, query)
    if not found:
        await message.answer(
            "❌ Игрок не найден",
            reply_markup=back_kb("admin_main"),
        )
        return

    from app.repositories.title_repo import title_repo
    titles_str = await title_repo.get_titles_display(session, found.id)

    await message.answer(
        f"👤 <b>{found.full_name}</b>\n"
        f"🆔 tg_id: <code>{found.tg_id}</code>\n"
        f"🏴 Банда: {found.gang_name or '—'}\n"
        f"{phase_label(found.phase)}\n"
        f"⚔️ Мощь: {fmt_power(found.combat_power)}\n"
        f"💰 Монеты: {fmt_num(found.nh_coins)}\n"
        f"🎟 Тикеты: {found.tickets}/{found.max_tickets}\n"
        f"🌟 Пробуждений: {found.prestige_level}\n"
        f"💎 Титулы:\n{titles_str}",
        reply_markup=admin_user_kb(found.tg_id),
        parse_mode="HTML",
    )


# ── Действия с игроком ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_user:"))
async def cb_adm_user(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    try:
        await cb.message.edit_text(
            f"👤 {found.full_name} | {phase_label(found.phase)}\n"
            f"⚔️ {fmt_power(found.combat_power)} | 💰 {fmt_num(found.nh_coins)}",
            reply_markup=admin_user_kb(tg_id),
            parse_mode="HTML",
        )
    except Exception:
        pass


# ── Донатные титулы ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_title:"))
async def cb_adm_title(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await cb.message.edit_text(
        "💎 Выберите сет:",
        reply_markup=titles_grant_kb(int(tg_id)),
        parse_mode="HTML",
    )


async def _show_set_panel(
    message, session: AsyncSession, user: User,
    tg_id: int, set_id: str, found_user
):
    from app.data.titles import DONAT_TITLE_MAP, DONAT_TITLES, DONAT_SET_MAP
    from app.models.title import UserDonatTitle

    s = DONAT_SET_MAP.get(set_id)
    owned_r = await session.execute(
        select(UserDonatTitle.title_id).where(
            UserDonatTitle.user_id == found_user.id
        )
    )
    owned = set(owned_r.scalars().all())
    titles_in_set = [t for t in DONAT_TITLES if t.set_id == set_id]

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"🔱 Выдать весь сет ({s.name if s else set_id})",
        callback_data=f"adm_grantset_all:{tg_id}:{set_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="─── Отдельные титулы ───",
        callback_data="noop"
    ))
    for t in titles_in_set:
        status = "✅" if t.title_id in owned else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{status} {t.emoji} {t.name} — {t.price_rub}₽",
            callback_data=f"adm_grant_title:{tg_id}:{t.title_id}"
        ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data=f"adm_title:{tg_id}"
    ))

    lines = [f"📦 <b>{s.name if s else set_id}</b>\n"]
    for t in titles_in_set:
        status = "✅" if t.title_id in owned else "❌"
        lines.append(f"{status} {t.emoji} {t.name}\n  {t.bonus_description}")

    try:
        await message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_grantset:"))
async def cb_adm_grantset(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id = int(parts[1])
    set_id = parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    await _show_set_panel(cb.message, session, user, tg_id, set_id, found)


@router.callback_query(F.data.startswith("adm_grantset_all:"))
async def cb_adm_grantset_all(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id = int(parts[1])
    set_id = parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    from app.data.titles import DONAT_TITLES, DONAT_SET_MAP
    s = DONAT_SET_MAP.get(set_id)
    title_ids = [t.title_id for t in DONAT_TITLES if t.set_id == set_id]
    count = 0
    for tid in title_ids:
        result = await title_service.grant_title(session, found, tid, user.tg_id)
        if result["ok"]:
            count += 1

    await cb.answer(f"✅ Выдано {count} титулов!")
    await _show_set_panel(cb.message, session, user, tg_id, set_id, found)


@router.callback_query(F.data.startswith("adm_grant_title:"))
async def cb_adm_grant_title(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id = int(parts[1])
    title_id = parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    result = await title_service.grant_title(session, found, title_id, user.tg_id)
    if result["ok"]:
        await cb.answer(f"✅ {result['title']} выдан!")
    else:
        await cb.answer(result["reason"], show_alert=True)

    from app.data.titles import DONAT_TITLE_MAP
    cfg = DONAT_TITLE_MAP.get(title_id)
    if cfg:
        await _show_set_panel(cb.message, session, user, tg_id, cfg.set_id, found)


@router.callback_query(F.data.startswith("adm_untitle:"))
async def cb_adm_untitle(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    owned = await title_service.get_user_titles(session, found.id)
    if not owned:
        await cb.answer("У игрока нет титулов", show_alert=True)
        return

    from app.data.titles import DONAT_TITLE_MAP
    builder = InlineKeyboardBuilder()
    for tid in owned:
        cfg = DONAT_TITLE_MAP.get(tid)
        if cfg:
            builder.row(InlineKeyboardButton(
                text=f"❌ {cfg.emoji} {cfg.name}",
                callback_data=f"adm_revoke:{tg_id}:{tid}"
            ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data=f"adm_user:{tg_id}"
    ))
    await cb.message.edit_text(
        f"❌ Выберите титул для снятия с {found.full_name}:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_revoke:"))
async def cb_adm_revoke(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id = int(parts[1])
    title_id = parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    result = await title_service.revoke_title(session, found, title_id)
    if result["ok"]:
        await cb.answer("✅ Титул снят")
        # Перерисовываем список напрямую
        owned = await title_service.get_user_titles(session, found.id)
        from app.data.titles import DONAT_TITLE_MAP
        builder = InlineKeyboardBuilder()
        for tid in owned:
            cfg = DONAT_TITLE_MAP.get(tid)
            if cfg:
                builder.row(InlineKeyboardButton(
                    text=f"❌ {cfg.emoji} {cfg.name}",
                    callback_data=f"adm_revoke:{tg_id}:{tid}"
                ))
        builder.row(InlineKeyboardButton(
            text="◀️ Назад", callback_data=f"adm_user:{tg_id}"
        ))
        try:
            await cb.message.edit_text(
                f"❌ Выберите титул для снятия с {found.full_name}:",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        await cb.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("adm_coins:"))
async def cb_adm_coins(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await state.set_state(AdminFSM.waiting_coins)
    await state.update_data(target_tg_id=tg_id)
    await cb.message.edit_text(
        f"💰 Введите количество монет для игрока {tg_id}:",
        reply_markup=back_kb(f"adm_user:{tg_id}"),
    )


@router.message(AdminFSM.waiting_coins)
async def msg_adm_coins(
    message: Message, session: AsyncSession,
    user: User, state: FSMContext
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
        f"✅ Выдано {fmt_num(amount)} монет игроку {found.full_name}",
        reply_markup=back_kb("admin_main"),
    )


@router.callback_query(F.data.startswith("adm_tickets:"))
async def cb_adm_tickets(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await state.set_state(AdminFSM.waiting_tickets)
    await state.update_data(target_tg_id=tg_id)
    await cb.message.edit_text(
        f"🎟 Введите количество тикетов:",
        reply_markup=back_kb(f"adm_user:{tg_id}"),
    )


@router.message(AdminFSM.waiting_tickets)
async def msg_adm_tickets(
    message: Message, session: AsyncSession,
    user: User, state: FSMContext
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
        f"✅ Выдано {count} тикетов игроку {found.full_name}",
        reply_markup=back_kb("admin_main"),
    )


@router.callback_query(F.data.startswith("adm_tui:"))
async def cb_adm_tui(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    await admin_service.give_tui(session, found)
    await cb.answer(f"✅ TUI выдан {found.full_name}")


@router.callback_query(F.data.startswith("adm_untui:"))
async def cb_adm_untui(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    await admin_service.remove_tui(session, found)
    await cb.answer(f"✅ TUI снят с {found.full_name}")


@router.callback_query(F.data.startswith("adm_all:"))
async def cb_adm_all(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    count = await admin_service.give_all_titles(session, found, user.tg_id)
    await cb.answer(f"🔱 Выдано {count} титулов!")


@router.callback_query(F.data.startswith("adm_none:"))
async def cb_adm_none(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    await admin_service.remove_all_titles(session, found)
    await cb.answer(f"💀 Все титулы сняты!")


# ── Патч ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_patch")
async def cb_admin_patch(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_patch_version)
    await cb.message.edit_text(
        "🔧 <b>Патч — сброс прогресса</b>\n\n"
        "Введите версию патча в формате <code>1.0.1</code>\n\n"
        "⚠️ Донаты и пробуждения сохранятся.\n"
        "Весь прогресс игроков будет сброшен!",
        reply_markup=back_kb("admin_main"),
        parse_mode="HTML",
    )


@router.message(AdminFSM.waiting_patch_version)
async def msg_patch_version(
    message: Message, session: AsyncSession,
    user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    version = message.text.strip()

    import re
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        await message.answer(
            "❌ Неверный формат. Введите версию как <code>1.0.1</code>",
            parse_mode="HTML",
        )
        return

    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"✅ Подтвердить патч {version}",
        callback_data=f"admin_patch_confirm:{version}"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Отмена", callback_data="admin_main"
    ))

    await message.answer(
        f"⚠️ <b>Подтвердить патч {version}?</b>\n\n"
        f"Прогресс ВСЕХ игроков будет сброшен!\n"
        f"Донаты и пробуждения сохранятся.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("admin_patch_confirm:"))
async def cb_admin_patch_confirm(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    if not is_admin(user.tg_id):
        return
    version = cb.data.split(":", 1)[1]
    count = await admin_service.patch_reset_progress(session, version)

    # Используем bot из callback
    bot = cb.bot

    from app.models.user import User as UserModel
    users_r = await session.execute(
        select(UserModel).where(UserModel.notifications_enabled == True)
    )
    for u in users_r.scalars().all():
        try:
            await bot.send_message(
                u.tg_id,
                f"🔧 <b>Патч {version} применён!</b>\n\n"
                f"Прогресс всех игроков сброшен.\n"
                f"Донаты и пробуждения сохранены.\n\n"
                f"Удачи в новом старте! 💪",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await cb.message.edit_text(
        f"✅ <b>Патч {version} применён!</b>\n\nСброшено: {count} игроков",
        reply_markup=back_kb("admin_main"),
        parse_mode="HTML",
    )


# ── Бэкапы ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_backup")
async def cb_admin_backup(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    backups = await admin_service.list_backups()

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💾 Создать новый бэкап",
        callback_data="admin_backup_create"
    ))
    if backups:
        builder.row(InlineKeyboardButton(
            text="─── Восстановить из ───",
            callback_data="noop"
        ))
        for b in backups[:8]:
            builder.row(InlineKeyboardButton(
                text=f"📁 {b['name']} ({b['size_kb']} KB)",
                callback_data=f"admin_restore:{b['name']}"
            ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="admin_main"
    ))

    backup_list = "\n".join(
        f"  📁 {b['name']} — {b['size_kb']} KB" for b in backups[:8]
    ) if backups else "  Бэкапов нет"

    await cb.message.edit_text(
        f"💾 <b>Бэкапы</b>\n\nСписок бэкапов:\n{backup_list}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_backup_create")
async def cb_admin_backup_create(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    await cb.answer("⏳ Создаю бэкап...")
    result = await admin_service.create_backup()
    if result["ok"]:
        await cb.message.edit_text(
            f"✅ <b>Бэкап создан!</b>\n\n"
            f"Файл: <code>{result['filename']}</code>\n"
            f"Размер: {result['size_kb']} KB",
            reply_markup=back_kb("admin_backup"),
            parse_mode="HTML",
        )
    else:
        await cb.message.edit_text(
            f"❌ Ошибка создания бэкапа",
            reply_markup=back_kb("admin_backup"),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("admin_restore:"))
async def cb_admin_restore(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    filename = cb.data.split(":", 1)[1]

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="⚠️ Подтвердить восстановление",
        callback_data=f"admin_restore_confirm:{filename}"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Отмена", callback_data="admin_backup"
    ))

    await cb.message.edit_text(
        f"⚠️ <b>Восстановление из бэкапа</b>\n\n"
        f"Файл: <code>{filename}</code>\n\n"
        f"❗ Текущие данные будут перезаписаны!\n"
        f"Подтвердить?",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("admin_restore_confirm:"))
async def cb_admin_restore_confirm(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    if not is_admin(user.tg_id):
        return
    filename = cb.data.split(":", 1)[1]
    filepath = f"/app/backups/{filename}"
    await cb.answer("⏳ Восстанавливаю...")
    result = await admin_service.restore_backup(filepath)
    if result["ok"]:
        await cb.message.edit_text(
            f"✅ <b>Восстановлено из {filename}</b>",
            reply_markup=back_kb("admin_main"),
            parse_mode="HTML",
        )
    else:
        await cb.message.edit_text(
            f"❌ Ошибка восстановления\n{result.get('reason','')}",
            reply_markup=back_kb("admin_backup"),
            parse_mode="HTML",
        )


# ── Рассылка ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_broadcast)
    await cb.message.edit_text(
        "📢 <b>Рассылка всем игрокам</b>\n\n"
        "Введите текст сообщения.\n"
        "Поддерживается HTML-форматирование.",
        reply_markup=back_kb("admin_main"),
        parse_mode="HTML",
    )


@router.message(AdminFSM.waiting_broadcast)
async def msg_broadcast(
    message: Message, session: AsyncSession,
    user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    await state.clear()
    text = message.text.strip()

    from app.models.user import User as UserModel

    users_r = await session.execute(select(UserModel))
    all_users = users_r.scalars().all()

    # Берём бот из самого сообщения — он всегда доступен
    bot = message.bot

    sent = 0
    failed = 0
    blocked = 0

    for u in all_users:
        try:
            await bot.send_message(
                u.tg_id,
                f"📢 <b>Сообщение от администрации</b>\n\n{text}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception as e:
            err = str(e).lower()
            if "blocked" in err or "forbidden" in err or "deactivated" in err:
                blocked += 1
            else:
                failed += 1

    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"👥 Всего: {len(all_users)}\n"
        f"✅ Отправлено: {sent}\n"
        f"🚫 Заблокировали: {blocked}\n"
        f"❌ Ошибки: {failed}",
        reply_markup=back_kb("admin_main"),
    )

# ── Действия со всеми ───────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_bulk")
async def cb_admin_bulk(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💰 Выдать монеты всем", callback_data="admin_bulk_coins"
    ))
    builder.row(InlineKeyboardButton(
        text="🎟 Выдать тикеты всем", callback_data="admin_bulk_tickets"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="admin_main"
    ))
    try:
        await cb.message.edit_text(
            "👥 <b>Действия со всеми игроками</b>\n\nВыбери действие:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_bulk_coins")
async def cb_admin_bulk_coins(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_bulk_coins)
    await cb.message.edit_text(
        "💰 Введите количество монет для всех игроков:",
        reply_markup=back_kb("admin_bulk"),
    )


@router.message(AdminFSM.waiting_bulk_coins)
async def msg_bulk_coins(
    message: Message, session: AsyncSession,
    user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    await state.clear()
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число")
        return

    from app.models.user import User as UserModel
    users_r = await session.execute(select(UserModel))
    users = users_r.scalars().all()
    for u in users:
        u.nh_coins += amount
    await session.flush()

    await message.answer(
        f"✅ Выдано {fmt_num(amount)} монет {len(users)} игрокам!",
        reply_markup=back_kb("admin_main"),
    )


@router.callback_query(F.data == "admin_bulk_tickets")
async def cb_admin_bulk_tickets(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_bulk_tickets)
    await cb.message.edit_text(
        "🎟 Введите количество тикетов для всех игроков:",
        reply_markup=back_kb("admin_bulk"),
    )


@router.message(AdminFSM.waiting_bulk_tickets)
async def msg_bulk_tickets(
    message: Message, session: AsyncSession,
    user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    await state.clear()
    try:
        count = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число")
        return

    from app.models.user import User as UserModel
    users_r = await session.execute(select(UserModel))
    users = users_r.scalars().all()
    for u in users:
        u.tickets += count
    await session.flush()

    await message.answer(
        f"✅ Выдано {count} тикетов {len(users)} игрокам!",
        reply_markup=back_kb("admin_main"),
    )


# ── Утилиты ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()