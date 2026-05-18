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
from app.services.promo_service import promo_service, REWARD_LABELS
from app.utils.keyboards.admin import admin_main_kb, admin_user_kb, titles_grant_kb
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num, fmt_power, phase_label
from app.config import settings
import html

router = Router()


def is_admin(tg_id: int) -> bool:
    return tg_id in settings.admin_ids_list


class AdminFSM(StatesGroup):
    waiting_search = State()
    waiting_coins = State()
    waiting_tickets = State()
    waiting_patch_version = State()
    waiting_version_only = State()
    waiting_broadcast = State()
    waiting_bulk_coins = State()
    waiting_bulk_tickets = State()
    waiting_promo_create = State()
    waiting_clan_donat_search = State()
    waiting_mastery_points = State()
    waiting_path_points = State()
    waiting_ui_fragments = State()
    waiting_alchemy_fragments = State()
    waiting_squad_count = State()


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

    try:
        await cb.message.edit_text(
            f"📊 <b>Статистика</b>\n\n"
            f"Всего игроков: {stats['total']}\n"
            f"⚔️ С боевой мощью > 0: {stats['with_power']}\n"
            f"🔖 {version_str}\n\n"
            f"По фазам:\n{phase_lines}",
            reply_markup=back_kb("admin_main"),
            parse_mode="HTML",
        )
    except Exception:
        pass


# ── Поиск игрока ────────────────────────────────────────────────────────────

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


async def _show_user_card(message, session, found):
    from app.repositories.title_repo import title_repo
    titles_str = await title_repo.get_titles_display(session, found.id)
    try:
        await message.edit_text(
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
    except Exception:
        pass


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


# ── Монеты ──────────────────────────────────────────────────────────────────

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


# ── Тикеты ──────────────────────────────────────────────────────────────────

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


# ── Донатные титулы ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_title:"))
async def cb_adm_title(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    try:
        await cb.message.edit_text(
            "💎 Выберите сет:",
            reply_markup=titles_grant_kb(int(tg_id)),
            parse_mode="HTML",
        )
    except Exception:
        pass


async def _show_set_panel(message, session, user, tg_id, set_id, found_user):
    from app.data.titles import DONAT_TITLE_MAP, DONAT_TITLES, DONAT_SET_MAP
    from app.models.title import UserDonatTitle

    s = DONAT_SET_MAP.get(set_id)
    owned_r = await session.execute(
        select(UserDonatTitle.title_id).where(UserDonatTitle.user_id == found_user.id)
    )
    owned = set(owned_r.scalars().all())
    titles_in_set = [t for t in DONAT_TITLES if t.set_id == set_id]

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"🔱 Выдать весь сет ({s.name if s else set_id})",
        callback_data=f"adm_grantset_all:{tg_id}:{set_id}"
    ))
    builder.row(InlineKeyboardButton(text="─── Отдельные титулы ───", callback_data="noop"))
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
    tg_id, set_id = int(parts[1]), parts[2]
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
    tg_id, set_id = int(parts[1]), parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    from app.data.titles import DONAT_TITLES
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
    tg_id, title_id = int(parts[1]), parts[2]
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


async def _render_untitle(message, session: AsyncSession, tg_id: int, found) -> None:
    from app.data.titles import DONAT_SETS, DONAT_TITLES
    owned = set(await title_service.get_user_titles(session, found.id))
    if not owned:
        try:
            await message.edit_text(
                f"У {html.escape(found.full_name)} нет титулов",
                reply_markup=InlineKeyboardBuilder().row(
                    InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_user:{tg_id}")
                ).as_markup(),
            )
        except Exception:
            pass
        return
    builder = InlineKeyboardBuilder()
    for s in DONAT_SETS:
        titles_in_set = [t for t in DONAT_TITLES if t.set_id == s.set_id]
        owned_in_set = [t for t in titles_in_set if t.title_id in owned]
        if not owned_in_set:
            continue
        count_str = f"{len(owned_in_set)}/{len(titles_in_set)}"
        builder.row(InlineKeyboardButton(
            text=f"📦 {s.name} [{count_str}]",
            callback_data=f"adm_untset:{tg_id}:{s.set_id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_user:{tg_id}"))
    try:
        await message.edit_text(
            f"❌ <b>Снятие титулов</b> — {html.escape(found.full_name)}\n\nВыбери сет:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


async def _render_untset(message, session: AsyncSession, tg_id: int, set_id: str, found) -> None:
    from app.data.titles import DONAT_TITLES, DONAT_SET_MAP
    owned = set(await title_service.get_user_titles(session, found.id))
    set_cfg = DONAT_SET_MAP.get(set_id)
    titles_in_set = [t for t in DONAT_TITLES if t.set_id == set_id]
    owned_in_set = [t for t in titles_in_set if t.title_id in owned]
    if not owned_in_set:
        await _render_untitle(message, session, tg_id, found)
        return
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"🗑 Снять весь сет ({len(owned_in_set)} шт.)",
        callback_data=f"adm_revset:{tg_id}:{set_id}"
    ))
    for t in owned_in_set:
        builder.row(InlineKeyboardButton(
            text=f"❌ {t.emoji} {t.name}",
            callback_data=f"adm_revoke:{tg_id}:{t.title_id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_untitle:{tg_id}"))
    set_name = set_cfg.name if set_cfg else set_id
    try:
        await message.edit_text(
            f"📦 <b>{html.escape(set_name)}</b> — {html.escape(found.full_name)}\n\nВыбери что снять:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_untitle:"))
async def cb_adm_untitle(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    await _render_untitle(cb.message, session, tg_id, found)


@router.callback_query(F.data.startswith("adm_untset:"))
async def cb_adm_untset(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, set_id = int(parts[1]), parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    await _render_untset(cb.message, session, tg_id, set_id, found)


@router.callback_query(F.data.startswith("adm_revset:"))
async def cb_adm_revset(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, set_id = int(parts[1]), parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    removed = await title_service.revoke_set(session, found, set_id)
    await cb.answer(f"✅ Снято {removed} титулов", show_alert=True)
    await _render_untitle(cb.message, session, tg_id, found)


@router.callback_query(F.data.startswith("adm_revoke:"))
async def cb_adm_revoke(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, title_id = int(parts[1]), parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    from app.data.titles import DONAT_TITLE_MAP, DONAT_TITLES
    cfg = DONAT_TITLE_MAP.get(title_id)
    result = await title_service.revoke_title(session, found, title_id)
    if not result["ok"]:
        await cb.answer("Ошибка", show_alert=True)
        return
    await cb.answer("✅ Титул снят")
    if cfg:
        owned_after = set(await title_service.get_user_titles(session, found.id))
        remaining = [t for t in DONAT_TITLES if t.set_id == cfg.set_id and t.title_id in owned_after]
        if remaining:
            await _render_untset(cb.message, session, tg_id, cfg.set_id, found)
            return
    await _render_untitle(cb.message, session, tg_id, found)


# ── TUI ─────────────────────────────────────────────────────────────────────

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
    await _show_user_card(cb.message, session, found)


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
    await _show_user_card(cb.message, session, found)


# ── Пробуждения ─────────────────────────────────────────────────────────────

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
    await cb.answer("💀 Все титулы сняты!")


# ── Ресурсы ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_resources:"))
async def cb_adm_resources(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⭐ Очки мастерства", callback_data=f"adm_mastery:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🔷 Очки пути", callback_data=f"adm_pathpts:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🔮 Фрагменты УИ", callback_data=f"adm_uifrag:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🧪 Фрагменты алхимии", callback_data=f"adm_alchfrag:{tg_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_user:{tg_id}"))
    try:
        await cb.message.edit_text("📦 Выберите ресурс для выдачи:", reply_markup=builder.as_markup())
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_mastery:"))
async def cb_adm_mastery(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await state.set_state(AdminFSM.waiting_mastery_points)
    await state.update_data(target_tg_id=tg_id)
    try:
        await cb.message.edit_text(f"⭐ Введите количество очков мастерства:", reply_markup=back_kb(f"adm_resources:{tg_id}"))
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
    await message.answer(f"✅ Выдано {amount} очков мастерства игроку {html.escape(found.full_name)}", parse_mode="HTML")
    await _show_user_card(message, session, found)


@router.callback_query(F.data.startswith("adm_pathpts:"))
async def cb_adm_pathpts(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await state.set_state(AdminFSM.waiting_path_points)
    await state.update_data(target_tg_id=tg_id)
    try:
        await cb.message.edit_text(f"🔷 Введите количество очков пути:", reply_markup=back_kb(f"adm_resources:{tg_id}"))
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
    await message.answer(f"✅ Выдано {amount} очков пути игроку {html.escape(found.full_name)}", parse_mode="HTML")
    await _show_user_card(message, session, found)


@router.callback_query(F.data.startswith("adm_uifrag:"))
async def cb_adm_uifrag(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await state.set_state(AdminFSM.waiting_ui_fragments)
    await state.update_data(target_tg_id=tg_id)
    try:
        await cb.message.edit_text(f"🔮 Введите количество фрагментов УИ:", reply_markup=back_kb(f"adm_resources:{tg_id}"))
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
    await message.answer(f"✅ Выдано {amount} фрагментов УИ игроку {html.escape(found.full_name)}", parse_mode="HTML")
    await _show_user_card(message, session, found)


@router.callback_query(F.data.startswith("adm_alchfrag:"))
async def cb_adm_alchfrag(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    await state.set_state(AdminFSM.waiting_alchemy_fragments)
    await state.update_data(target_tg_id=tg_id)
    try:
        await cb.message.edit_text(f"🧪 Введите количество фрагментов алхимии:", reply_markup=back_kb(f"adm_resources:{tg_id}"))
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
    await message.answer(f"✅ Выдано {amount} фрагментов алхимии игроку {html.escape(found.full_name)}", parse_mode="HTML")
    await _show_user_card(message, session, found)


# ── Удаление аккаунта ────────────────────────────────────────────────────────

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


# ── Патч ────────────────────────────────────────────────────────────────────

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

    # Получаем топ ДО сброса для уведомлений
    from sqlalchemy import select
    from app.models.user import User as UserModel
    from app.models.clan import Clan, ClanMember

    top_r = await session.execute(
        select(UserModel).order_by(UserModel.combat_power.desc()).limit(10)
    )
    top_players = top_r.scalars().all()
    top_rewards = {0: 10, 1: 9, 2: 8, 3: 7, 4: 6, 5: 5, 6: 4, 7: 4, 8: 3, 9: 3}

    top_clans_r = await session.execute(
        select(Clan).order_by(Clan.combat_power.desc()).limit(5)
    )
    top_clans = top_clans_r.scalars().all()
    clan_rewards = {0: 8, 1: 6, 2: 5, 3: 4, 4: 3}

    count = await admin_service.patch_reset_progress(session, version)
    bot = cb.bot

    # Рассылка всем
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

    # Уведомляем топ-10 игроков
    for i, u in enumerate(top_players):
        tickets = top_rewards.get(i, 3)
        try:
            await bot.send_message(
                u.tg_id,
                f"🏆 <b>Награда за топ-{i+1} перед патчем!</b>\n\n"
                f"Вы заняли <b>#{i+1} место</b> по боевой мощи.\n"
                f"🎟 Получено: <b>+{tickets} тикетов</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass

    # Уведомляем топ-5 кланов
    for i, clan in enumerate(top_clans):
        tickets = clan_rewards.get(i, 3)
        members_r = await session.execute(
            select(ClanMember).where(ClanMember.clan_id == clan.id)
        )
        for member in members_r.scalars().all():
            member_user = await session.scalar(
                select(UserModel).where(UserModel.id == member.user_id)
            )
            if not member_user:
                continue
            try:
                await bot.send_message(
                    member_user.tg_id,
                    f"🏯 <b>Награда клану {html.escape(clan.name)} за топ-{i+1}!</b>\n\n"
                    f"Ваш клан занял <b>#{i+1} место</b> по боевой мощи.\n"
                    f"🎟 Получено: <b>+{tickets} тикетов</b>\n"
                    f"🏦 Казна клана обнулена.",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    try:
        await cb.message.edit_text(
            f"✅ <b>Патч {version} применён!</b>\n\n"
            f"Сброшено: {count} игроков\n"
            f"🏆 Топ-10 игроков получили тикеты\n"
            f"🏯 Топ-5 кланов получили тикеты, казны обнулены",
            reply_markup=back_kb("admin_main"),
            parse_mode="HTML",
        )
    except Exception:
        pass


# ── Промокоды ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_promos")
async def cb_admin_promos(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    promos = await promo_service.get_all_promos(session)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="➕ Создать промокод", callback_data="admin_promo_create"
    ))
    for p in promos:
        status = "✅" if p.is_active else "❌"
        label = REWARD_LABELS.get(p.reward_type, p.reward_type)
        builder.row(InlineKeyboardButton(
            text=f"{status} {p.code} | {label} ×{p.reward_amount} ({p.used_count}/{p.max_uses})",
            callback_data=f"admin_promo_info:{p.id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main"))

    try:
        await cb.message.edit_text(
            f"🎁 <b>Промокоды</b>\n\nВсего: {len(promos)}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_promo_create")
async def cb_admin_promo_create(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_promo_create)

    types_str = "\n".join(f"  <code>{k}</code> — {v}" for k, v in REWARD_LABELS.items())
    try:
        await cb.message.edit_text(
            f"➕ <b>Создать промокод</b>\n\n"
            f"Введите в формате:\n"
            f"<code>КОД ТИП КОЛИЧЕСТВО МАКС_ИСПОЛЬЗОВАНИЙ</code>\n\n"
            f"Например:\n"
            f"<code>OLDNHSTARTERS coins 100000 50</code>\n"
            f"<code>WELCOME tickets 5 1</code>\n\n"
            f"Типы наград:\n{types_str}",
            reply_markup=back_kb("admin_promos"),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_promo_create)
async def msg_promo_create(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    await state.clear()
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.answer(
            "❌ Неверный формат. Пример:\n<code>PROMO coins 100000 50</code>",
            parse_mode="HTML",
            reply_markup=back_kb("admin_promos"),
        )
        return
    code = parts[0]
    reward_type = parts[1]
    try:
        reward_amount = int(parts[2])
        max_uses = int(parts[3]) if len(parts) > 3 else 1
    except ValueError:
        await message.answer("❌ Количество должно быть числом")
        return

    result = await promo_service.create_promo(
        session, code, reward_type, reward_amount, max_uses
    )
    if result["ok"]:
        label = REWARD_LABELS.get(reward_type, reward_type)
        await message.answer(
            f"✅ Промокод создан!\n\n"
            f"Код: <code>{code.upper()}</code>\n"
            f"Награда: {label} ×{reward_amount}\n"
            f"Макс. использований: {max_uses}",
            reply_markup=back_kb("admin_promos"),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"❌ {result['reason']}",
            reply_markup=back_kb("admin_promos"),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("admin_promo_info:"))
async def cb_admin_promo_info(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    promo_id = int(cb.data.split(":")[1])
    from app.models.promo import PromoCode
    promo = await session.scalar(
        select(PromoCode).where(PromoCode.id == promo_id)
    )
    if not promo:
        await cb.answer("Промокод не найден", show_alert=True)
        return

    label = REWARD_LABELS.get(promo.reward_type, promo.reward_type)
    builder = InlineKeyboardBuilder()
    if promo.is_active:
        builder.row(InlineKeyboardButton(
            text="❌ Деактивировать",
            callback_data=f"admin_promo_deactivate:{promo_id}"
        ))
    builder.row(InlineKeyboardButton(
        text="🗑 Удалить",
        callback_data=f"admin_promo_delete:{promo_id}"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_promos"))

    try:
        await cb.message.edit_text(
            f"🎁 <b>Промокод {promo.code}</b>\n\n"
            f"Тип: {label}\n"
            f"Количество: {fmt_num(promo.reward_amount)}\n"
            f"Использований: {promo.used_count}/{promo.max_uses}\n"
            f"Статус: {'✅ Активен' if promo.is_active else '❌ Неактивен'}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("admin_promo_deactivate:"))
async def cb_admin_promo_deactivate(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    promo_id = int(cb.data.split(":")[1])
    result = await promo_service.deactivate_promo(session, promo_id)
    if result["ok"]:
        await cb.answer("✅ Промокод деактивирован")
    else:
        await cb.answer(result["reason"], show_alert=True)
    await cb_admin_promos(cb, session, user)


@router.callback_query(F.data.startswith("admin_promo_delete:"))
async def cb_admin_promo_delete(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    promo_id = int(cb.data.split(":")[1])
    result = await promo_service.delete_promo(session, promo_id)
    if result["ok"]:
        await cb.answer("🗑 Промокод удалён")
    else:
        await cb.answer(result["reason"], show_alert=True)
    await cb_admin_promos(cb, session, user)


# ── Бэкапы ──────────────────────────────────────────────────────────────────

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


# ── Рассылка ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_broadcast)
    try:
        await cb.message.edit_text(
            "📢 <b>Рассылка всем игрокам</b>\n\n"
            "Введите текст сообщения.\nПоддерживается HTML-форматирование.",
            reply_markup=back_kb("admin_main"),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_broadcast)
async def msg_broadcast(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    await state.clear()
    text = message.text.strip()
    from app.models.user import User as UserModel
    users_r = await session.execute(select(UserModel))
    all_users = users_r.scalars().all()
    bot = message.bot
    sent = failed = blocked = 0
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
    builder.row(InlineKeyboardButton(text="💰 Выдать монеты всем", callback_data="admin_bulk_coins"))
    builder.row(InlineKeyboardButton(text="🎟 Выдать тикеты всем", callback_data="admin_bulk_tickets"))
    builder.row(InlineKeyboardButton(text="🔄 Пересчитать бонусы всем", callback_data="admin_bulk_reapply"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main"))
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
    try:
        await cb.message.edit_text(
            "💰 Введите количество монет для всех игроков:",
            reply_markup=back_kb("admin_bulk"),
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_bulk_coins)
async def msg_bulk_coins(
    message: Message, session: AsyncSession, user: User, state: FSMContext
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
    try:
        await cb.message.edit_text(
            "🎟 Введите количество тикетов для всех игроков:",
            reply_markup=back_kb("admin_bulk"),
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_bulk_tickets)
async def msg_bulk_tickets(
    message: Message, session: AsyncSession, user: User, state: FSMContext
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


@router.callback_query(F.data == "admin_bulk_reapply")
async def cb_admin_bulk_reapply(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    from app.models.user import User as UserModel
    from app.services.title_service import title_service as ts
    users_r = await session.execute(select(UserModel))
    users = users_r.scalars().all()
    for u in users:
        await ts.reapply_all_titles(session, u)
    await cb.answer(f"✅ Бонусы пересчитаны для {len(users)} игроков", show_alert=True)
    try:
        await cb.message.edit_text(
            f"✅ Бонусы пересчитаны для {len(users)} игроков",
            reply_markup=back_kb("admin_bulk"),
        )
    except Exception:
        pass


# ── Клан-донат ──────────────────────────────────────────────────────────────

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
    from sqlalchemy import select as sa_select
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


async def _show_clan_donat_panel(message, clan):
    from app.constants.clan import CLAN_DONAT_PACKAGES
    active = []
    if clan.donat_income_pct: active.append(f"💰 Доход +{clan.donat_income_pct}%")
    if clan.donat_ticket_pct: active.append(f"🍀 Тикет +{clan.donat_ticket_pct}%")
    if clan.donat_train_pct:  active.append(f"🏋 Тренировка +{clan.donat_train_pct}%")
    active_str = "\n".join(active) if active else "нет"

    builder = InlineKeyboardBuilder()
    for pkg in CLAN_DONAT_PACKAGES:
        bonuses = []
        if pkg.income_pct:  bonuses.append(f"+{pkg.income_pct}% дох")
        if pkg.ticket_pct:  bonuses.append(f"+{pkg.ticket_pct}% тик")
        if pkg.train_pct:   bonuses.append(f"+{pkg.train_pct}% трен")
        builder.row(InlineKeyboardButton(
            text=f"{pkg.name} ({', '.join(bonuses)}) — {pkg.price_rub}₽",
            callback_data=f"adm_clan_donat_apply:{clan.id}:{pkg.package_id}"
        ))
    builder.row(InlineKeyboardButton(
        text="🗑 Сбросить донат-бонусы",
        callback_data=f"adm_clan_donat_reset:{clan.id}"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main"))

    text = (
        f"🏯 <b>Клан: {html.escape(clan.name)}</b>\n"
        f"👥 Участников: до {clan.max_members + clan.bonus_max_members}\n\n"
        f"<b>Текущий донат:</b>\n{active_str}\n\n"
        f"Выберите пакет для выдачи (значения накапливаются):"
    )
    try:
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_clan_donat_view:"))
async def cb_adm_clan_donat_view(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    clan_id = int(cb.data.split(":")[1])
    from sqlalchemy import select as sa_select
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
    from sqlalchemy import select as sa_select
    from app.models.clan import Clan
    from app.services.clan import clan_service
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
    from app.models.clan import ClanMember
    from app.models.user import User as UserModel
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


@router.callback_query(F.data.startswith("adm_clan_donat_reset:"))
async def cb_adm_clan_donat_reset(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    clan_id = int(cb.data.split(":")[1])
    from sqlalchemy import select as sa_select
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


# ── Анти-скрипт: разбан ────────────────────────────────────────────────────

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


# ── Абсолютные персонажи ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_chars:"))
async def cb_adm_chars(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    from app.data.characters import CHARACTERS
    absolutes = [c for c in CHARACTERS if c["rank"] == "absolute"]
    builder = InlineKeyboardBuilder()
    for i, char in enumerate(absolutes):
        builder.row(InlineKeyboardButton(
            text=f"⭐ {char['name']}",
            callback_data=f"adm_give_char:{tg_id}:{i}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_user:{tg_id}"))
    try:
        await cb.message.edit_text(
            "⭐ Выберите абсолютного персонажа для выдачи:",
            reply_markup=builder.as_markup(),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_give_char:"))
async def cb_adm_give_char(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, char_idx = int(parts[1]), int(parts[2])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    from app.data.characters import CHARACTERS
    absolutes = [c for c in CHARACTERS if c["rank"] == "absolute"]
    if char_idx >= len(absolutes):
        await cb.answer("Персонаж не найден", show_alert=True)
        return
    char_data = absolutes[char_idx]
    result = await admin_service.give_character(session, found, char_data["name"])
    if result["ok"]:
        await cb.answer(f"✅ {char_data['name']} выдан!")
        try:
            if found.notifications_enabled:
                await cb.bot.send_message(
                    found.tg_id,
                    f"⭐ <b>Вам выдан абсолютный персонаж!</b>\n\n"
                    f"<b>{html.escape(char_data['name'])}</b>\n"
                    f"💥 Мощь: {char_data['power']:,}",
                    parse_mode="HTML",
                )
        except Exception:
            pass
    else:
        await cb.answer(result["reason"], show_alert=True)


# ── Статисты ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_squads:"))
async def cb_adm_squads(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    from app.data.squad import RANKS
    builder = InlineKeyboardBuilder()
    for rank_cfg in RANKS:
        builder.row(InlineKeyboardButton(
            text=f"{rank_cfg.emoji} {rank_cfg.rank} — {rank_cfg.base_power:,} мощи",
            callback_data=f"adm_give_squad:{tg_id}:{rank_cfg.rank}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_user:{tg_id}"))
    try:
        await cb.message.edit_text(
            "👥 Выберите ранг статиста для выдачи:",
            reply_markup=builder.as_markup(),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_give_squad:"))
async def cb_adm_give_squad(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, rank = parts[1], parts[2]
    await state.set_state(AdminFSM.waiting_squad_count)
    await state.update_data(target_tg_id=tg_id, squad_rank=rank)
    from app.data.squad import RANKS_BY_ID
    rank_cfg = RANKS_BY_ID.get(rank)
    rank_label = f"{rank_cfg.emoji} {rank}" if rank_cfg else rank
    try:
        await cb.message.edit_text(
            f"👥 Введите количество статистов {rank_label} для выдачи:",
            reply_markup=back_kb(f"adm_squads:{tg_id}"),
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_squad_count)
async def msg_adm_give_squad(message: Message, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    data = await state.get_data()
    tg_id = data.get("target_tg_id")
    rank = data.get("squad_rank")
    await state.clear()
    try:
        count = int(message.text.strip())
        if count <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное число")
        return
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await message.answer("Игрок не найден")
        return
    result = await admin_service.give_squad_member(session, found, rank, count)
    if result["ok"]:
        await message.answer(
            f"✅ Выдано {count} статистов {rank} игроку {html.escape(found.full_name)}",
            parse_mode="HTML",
        )
        await _show_user_card(message, session, found)
    else:
        await message.answer(f"❌ {result['reason']}")


# ── Утилиты ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()