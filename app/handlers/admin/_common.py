import html
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.services.admin_service import admin_service
from app.services.title_service import title_service
from app.utils.keyboards.admin import admin_user_kb
from app.utils.formatters import fmt_num, fmt_power, phase_label


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
    waiting_path_fragments = State()
    # Карточки
    waiting_card_char = State()   # ввод имени персонажа
    waiting_card_level = State()  # ввод уровня 0-3
    waiting_dust_amount = State() # ввод количества пыли


async def _show_user_card(message, session, found):
    from app.repositories.title_repo import title_repo
    titles_str = await title_repo.get_titles_display(session, found.id)
    duel_cd = getattr(found, "donat_duel_cd", False)
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
            reply_markup=admin_user_kb(found.tg_id, donat_duel_cd=duel_cd),
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


async def _show_clan_donat_panel(message, clan):
    from app.constants.clan import CLAN_DONAT_PACKAGES
    from app.services.clan.donat import VVIP_MAX_LEVEL
    active = []
    if clan.donat_income_pct: active.append(f"💰 Доход +{clan.donat_income_pct}%")
    if clan.donat_ticket_pct: active.append(f"🍀 Тикет +{clan.donat_ticket_pct}%")
    if clan.donat_train_pct:  active.append(f"🏋 Тренировка +{clan.donat_train_pct}%")
    active_str = "\n".join(active) if active else "нет"

    vvip_level = getattr(clan, "vvip_level", 0)

    builder = InlineKeyboardBuilder()

    # Кнопка выдачи полного уровня VVIP
    if vvip_level < VVIP_MAX_LEVEL:
        builder.row(InlineKeyboardButton(
            text=f"👑 Выдать +1 уровень VVIP ({vvip_level}/{VVIP_MAX_LEVEL}) — весь круг",
            callback_data=f"adm_clan_vvip_level:{clan.id}"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text=f"✅ MAX VVIP достигнут ({VVIP_MAX_LEVEL}/{VVIP_MAX_LEVEL})",
            callback_data="noop"
        ))

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

    vvip_str = f"👑 <b>VVIP уровень: {vvip_level}/{VVIP_MAX_LEVEL}</b>\n" if vvip_level > 0 else ""
    text = (
        f"🏯 <b>Клан: {html.escape(clan.name)}</b>\n"
        f"👥 Участников: до {clan.max_members + clan.bonus_max_members}\n"
        f"{vvip_str}\n"
        f"<b>Текущий донат:</b>\n{active_str}\n\n"
        f"Выберите пакет для выдачи (значения накапливаются):"
    )
    try:
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
