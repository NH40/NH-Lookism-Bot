import html
import os
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case

from app.models.user import User
from app.models.clan import Clan, ClanMember
from app.models.clan_region import KoreanRegion, KoreanRegionWar, KoreanRegionWarParticipant, KoreanRegionActivity
from app.services.clan import clan_service
from app.services.clan.region import RANK_LABELS, REGION_WAR_MIN_SCORE, REGION_WAR_MAX_MEMBERS
from app.data.regions import REGION_BY_SLUG
from app.utils.formatters import fmt_num

router = Router()

_MAP_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "images", "map", "map.png")
)


async def _reply(cb: CallbackQuery, text: str, keyboard):
    """Универсальная замена edit_text/edit_caption.

    Если текущее сообщение — фото:
      - текст ≤ 1024 → edit_caption
      - текст > 1024  → удаляем фото, отправляем новое текстовое
    Если текущее сообщение — текст → edit_text.
    """
    if cb.message.photo:
        if len(text) <= 1024:
            try:
                await cb.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
                return
            except Exception:
                pass
        # Текст слишком длинный для caption — удаляем фото, шлём текст
        try:
            await cb.message.delete()
        except Exception:
            pass
        try:
            await cb.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            pass
        return

    try:
        await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        try:
            await cb.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            pass


def _bonus_line(region: KoreanRegion) -> str:
    cfg = REGION_BY_SLUG.get(region.slug)
    if not cfg:
        return "Без бонусов"
    owner = cfg.owner_bonus_text.replace("\n", "\n   ")
    member = cfg.member_bonus_text.replace("\n", "\n   ")
    lines = []
    if owner:
        lines.append(f"👑 <b>Главе:</b>\n   {owner}")
    if member:
        lines.append(f"👥 <b>Участникам:</b>\n   {member}")
    return "\n\n".join(lines) if lines else "Без бонусов"


# ── Карта регионов ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "clan_regions_map")
async def cb_regions_map(cb: CallbackQuery, session: AsyncSession, user: User):
    regions = await clan_service.get_all_regions(session)

    # Batch load: owner clans + active wars (2 queries instead of 2N)
    owner_clan_ids = {r.owner_clan_id for r in regions if r.owner_clan_id}
    if owner_clan_ids:
        clans_rows = (await session.execute(
            select(Clan.id, Clan.name).where(Clan.id.in_(owner_clan_ids))
        )).all()
        clans_map = {r.id: r.name for r in clans_rows}
    else:
        clans_map = {}

    region_ids = [r.id for r in regions]
    active_wars_rows = (await session.execute(
        select(KoreanRegionWar.region_id).where(
            KoreanRegionWar.region_id.in_(region_ids),
            KoreanRegionWar.is_finished == False,
        )
    )).scalars().all()
    war_region_ids = set(active_wars_rows)

    caption_lines = ["🗺 <b>Карта регионов Кореи</b>\n"]
    for r in regions:
        if r.owner_clan_id and r.owner_clan_id in clans_map:
            owner_str = f"🏯 {html.escape(clans_map[r.owner_clan_id])}"
        elif r.owner_clan_id:
            owner_str = "🏯 ?"
        else:
            owner_str = "⬜ Свободен"
        caption_lines.append(f"{r.emoji} <b>{r.name}</b> — {owner_str}")

    builder = InlineKeyboardBuilder()
    for r in regions:
        suffix = " ⚔️" if r.id in war_region_ids else ""
        builder.button(
            text=f"{r.emoji} {r.name}{suffix}",
            callback_data=f"clan_region_view:{r.id}",
        )
    builder.adjust(2)  # 2 кнопки в ряд
    builder.row(InlineKeyboardButton(text="🏆 Зал Славы", callback_data="region_hall_of_fame"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    caption = "\n".join(caption_lines)
    keyboard = builder.as_markup()
    map_path = os.path.normpath(_MAP_PATH)

    # Всегда пытаемся показать фото
    if cb.message.photo:
        # Редактируем существующее фото
        try:
            photo = FSInputFile(map_path)
            await cb.message.edit_media(
                InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML"),
                reply_markup=keyboard,
            )
            await cb.answer()
            return
        except Exception:
            pass
    else:
        # Текущее сообщение — текст: отправляем новое фото и удаляем старое
        try:
            photo = FSInputFile(map_path)
            await cb.message.answer_photo(
                photo, caption=caption, reply_markup=keyboard, parse_mode="HTML"
            )
            await cb.answer()
            try:
                await cb.message.delete()
            except Exception:
                pass
            return
        except Exception:
            pass

    # Последний вариант: просто текст (если фото недоступно)
    try:
        await cb.message.edit_text(caption, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await cb.message.answer(caption, reply_markup=keyboard, parse_mode="HTML")
    await cb.answer()


# ── Просмотр одного региона ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("clan_region_view:"))
async def cb_region_view(cb: CallbackQuery, session: AsyncSession, user: User):
    region_id = int(cb.data.split(":")[1])
    region = await clan_service.get_region_by_id(session, region_id)
    if not region:
        await cb.answer("Регион не найден", show_alert=True)
        return

    clan = await clan_service.get_user_clan(session, user.id)
    war = await clan_service.get_active_war_for_region(session, region_id)
    now = datetime.now(timezone.utc)

    # Владелец региона
    if region.owner_clan_id:
        owner_clan = await session.scalar(select(Clan).where(Clan.id == region.owner_clan_id))
        owner_str = f"🏯 <b>{html.escape(owner_clan.name)}</b>" if owner_clan else "🏯 Неизвестен"
    else:
        owner_str = "⬜ <i>Нет владельца</i>"

    bonuses = _bonus_line(region)

    war_str = ""
    if war:
        remaining = max(0, int((war.ends_at - now).total_seconds()))
        h, m = divmod(remaining // 60, 60)
        participants = await clan_service.get_war_participants(session, war.id)
        war_str = f"\n\n⚔️ <b>Идёт война!</b> Осталось: {h}ч {m}м\nУчастников: {len(participants)} клан(а)"

    text = (
        f"{region.emoji} <b>{region.name}</b>\n\n"
        f"ℹ️ {region.description}\n\n"
        f"Владелец: {owner_str}\n\n"
        f"<b>Бонусы:</b>\n{bonuses}"
        f"{war_str}"
    )

    builder = InlineKeyboardBuilder()

    if clan:
        clan_war = await clan_service.get_active_war_for_clan(session, clan.id)
        member = await session.scalar(
            select(ClanMember).where(
                ClanMember.clan_id == clan.id,
                ClanMember.user_id == user.id,
            )
        )
        rank = member.rank if member else "member"
        can_manage = rank in ("owner", "deputy")
        members_count = len(await clan_service.get_clan_members(session, clan.id))

        if can_manage and members_count <= REGION_WAR_MAX_MEMBERS:
            if war:
                # Есть активная война — можно присоединиться (если не участвуем)
                already_participating = await session.scalar(
                    select(KoreanRegionWarParticipant).where(
                        KoreanRegionWarParticipant.war_id == war.id,
                        KoreanRegionWarParticipant.clan_id == clan.id,
                    )
                )
                if not already_participating and not clan_war:
                    builder.row(InlineKeyboardButton(
                        text="⚔️ Вступить в войну",
                        callback_data=f"clan_region_join_war:{region_id}",
                    ))
                elif already_participating:
                    builder.row(InlineKeyboardButton(
                        text="📊 Статус войны",
                        callback_data=f"clan_region_war_status:{war.id}",
                    ))
            elif not clan_war and region.owner_clan_id != clan.id:
                builder.row(InlineKeyboardButton(
                    text="⚔️ Начать войну за регион",
                    callback_data=f"clan_region_attack:{region_id}",
                ))
            elif clan_war:
                builder.row(InlineKeyboardButton(
                    text="📊 Статус войны",
                    callback_data=f"clan_region_war_status:{clan_war.id}",
                ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_regions_map"))

    await _reply(cb, text, builder.as_markup())


# ── Начало войны за регион ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("clan_region_attack:"))
async def cb_region_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    region_id = int(cb.data.split(":")[1])
    region = await clan_service.get_region_by_id(session, region_id)
    if not region:
        await cb.answer("Регион не найден", show_alert=True)
        return

    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    result = await clan_service.start_region_war(session, clan, region, user.id)

    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    await session.commit()

    ends_at = result["ends_at"]
    h, m = divmod(int((ends_at - datetime.now(timezone.utc)).total_seconds()) // 60, 60)
    joined = result.get("joined", False)

    score_guide = (
        f"🎯 <b>Очки активности (макс на игрока: 152):</b>\n"
        f"  🗺 Завершить поход — <b>+4</b> × 3 = 12\n"
        f"  ⚔️ Атака Fist — <b>+4</b> × 3 = 12\n"
        f"  💀 Рейд-босс / Дуэль / Босс / King — <b>+3</b> × 5 = 15 каждое\n"
        f"  🏙 Атака Gang / Аукцион / Задание — <b>+2</b> × 5 = 10 каждое\n"
        f"  🏋 Тренировка / Найм — <b>+1</b> × 10 = 10 каждое\n"
        f"  🛒 Биржа / Банк — <b>+1</b> × 5 = 5 каждое"
    )

    prefix = "вступил в" if joined else "начал"
    text = (
        f"⚔️ <b>Клан {prefix} войну за {region.emoji} {region.name}!</b>\n\n"
        f"⏰ {'До конца' if joined else 'Длится'}: {h}ч {m}м\n\n"
        f"{score_guide}\n\n"
        f"🏆 Минимум <b>{REGION_WAR_MIN_SCORE} очков</b> для захвата!\n"
        + ("" if joined else "Другие кланы могут вступить в борьбу.")
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📊 Статус войны",
        callback_data=f"clan_region_war_status:{result['war_id']}",
    ))
    builder.row(InlineKeyboardButton(text="◀️ Карта", callback_data="clan_regions_map"))

    await _reply(cb, text, builder.as_markup())

    # Уведомляем членов клана
    from app.bot_instance import get_bot
    from app.scheduler.tasks.notifications import _send_notifications
    bot = get_bot()
    if bot:
        members = await clan_service.get_clan_members(session, clan.id)
        other_ids = [m.user_id for m in members if m.user_id != user.id]
        tg_ids = list((await session.execute(
            select(User.tg_id).where(User.id.in_(other_ids))
        )).scalars().all()) if other_ids else []
        notif = (
            f"⚔️ <b>Война за регион!</b>\n\n"
            f"Клан <b>{html.escape(clan.name)}</b> начал войну за "
            f"{region.emoji} <b>{region.name}</b>!\n\n"
            f"🎯 Каждое действие приносит <b>ОА</b> прямо сейчас:\n"
            f"  🏋 Тренировка ×1 (макс 10)\n"
            f"  ⚔️ Атака банды ×2 (макс 5)\n"
            f"  👑 Атака короля ×3 (макс 5)\n"
            f"  👊 Атака кулака ×4 (макс 3)\n"
            f"  🗡 Рейд ×3 (макс 5)  •  🏆 Кампания ×4 (макс 3)\n\n"
            f"Победитель получит регион и ОА в казну клана!"
        )
        await _send_notifications(bot, tg_ids, notif)


# ── Вступление в активную войну ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("clan_region_join_war:"))
async def cb_region_join_war(cb: CallbackQuery, session: AsyncSession, user: User):
    region_id = int(cb.data.split(":")[1])
    region = await clan_service.get_region_by_id(session, region_id)
    if not region:
        await cb.answer("Регион не найден", show_alert=True)
        return

    war = await clan_service.get_active_war_for_region(session, region_id)
    if not war:
        await cb.answer("Война уже завершена", show_alert=True)
        return

    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    result = await clan_service.join_region_war(session, clan, war, user.id)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    await session.commit()
    await cb.answer(f"✅ Клан вступил в войну за {region.name}!", show_alert=True)
    await _show_war_status(cb, session, war.id)


# ── Статус войны ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("clan_region_war_status:"))
async def cb_region_war_status(cb: CallbackQuery, session: AsyncSession, user: User):
    war_id = int(cb.data.split(":")[1])
    await _show_war_status(cb, session, war_id)


async def _show_war_status(cb: CallbackQuery, session: AsyncSession, war_id: int):
    """Внутренняя функция отображения статуса войны (чтобы вызывать без cb.data)."""
    # Нет изменений war_id — используется напрямую
    war = await session.scalar(select(KoreanRegionWar).where(KoreanRegionWar.id == war_id))
    if not war:
        await cb.answer("Война не найдена", show_alert=True)
        return

    region = await clan_service.get_region_by_id(session, war.region_id)
    participants = await clan_service.get_war_participants(session, war.id)
    now = datetime.now(timezone.utc)

    if war.is_finished:
        time_str = "Завершена"
    else:
        remaining = max(0, int((war.ends_at - now).total_seconds()))
        h, m = divmod(remaining // 60, 60)
        time_str = f"⏰ {h}ч {m}м"

    lines = [
        f"⚔️ <b>Война за {region.emoji if region else ''} {region.name if region else '?'}</b>\n",
        f"Статус: {time_str}\n",
        f"🎯 Порог победы: {REGION_WAR_MIN_SCORE} очков\n",
        "─" * 20,
    ]

    # Batch load participant clans (1 query instead of N)
    if participants:
        p_clan_ids = [p.clan_id for p in participants]
        p_clans_map = {c.id: c for c in (await session.execute(
            select(Clan).where(Clan.id.in_(p_clan_ids))
        )).scalars().all()}
    else:
        p_clans_map = {}

    for i, p in enumerate(participants, 1):
        p_clan = p_clans_map.get(p.clan_id)
        name = html.escape(p_clan.name) if p_clan else "?"
        filled = min(10, round(p.score * 10 / REGION_WAR_MIN_SCORE))
        bar = "🟩" * filled + "⬜" * (10 - filled)
        pct = min(100, int(p.score * 100 / REGION_WAR_MIN_SCORE))
        is_winner = war.is_finished and war.winner_clan_id == p.clan_id
        suffix = " 🏆" if is_winner else ""
        lines.append(f"{i}. <b>{name}</b>{suffix}\n   {bar} {p.score}/{REGION_WAR_MIN_SCORE} ({pct}%)")

    if not participants:
        lines.append("Нет участников")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Обновить", callback_data=f"clan_region_war_status:{war_id}"))
    if region:
        builder.row(InlineKeyboardButton(text="◀️ Регион", callback_data=f"clan_region_view:{region.id}"))
    builder.row(InlineKeyboardButton(text="🗺 Карта", callback_data="clan_regions_map"))

    await _reply(cb, "\n".join(lines), builder.as_markup())


# ── Управление рангами (только для владельца) ──────────────────────────────────

@router.callback_query(F.data == "clan_manage_ranks")
async def cb_manage_ranks(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan or clan.owner_id != user.id:
        await cb.answer("Только владелец клана может управлять рангами", show_alert=True)
        return

    members = await clan_service.get_clan_members(session, clan.id)
    other_member_ids = [m.user_id for m in members if m.user_id != user.id]
    if other_member_ids:
        users_map = {u.id: u for u in (await session.execute(
            select(User.id, User.full_name).where(User.id.in_(other_member_ids))
        )).all()}
    else:
        users_map = {}
    rank_by_uid = {m.user_id: m.rank for m in members}

    builder = InlineKeyboardBuilder()
    for uid in other_member_ids:
        u_row = users_map.get(uid)
        if not u_row:
            continue
        rank_label = RANK_LABELS.get(rank_by_uid.get(uid, "member"), rank_by_uid.get(uid, "member"))
        builder.row(InlineKeyboardButton(
            text=f"{rank_label} — {html.escape(u_row.full_name)}",
            callback_data=f"clan_rank_menu:{uid}",
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    await _reply(
        cb,
        f"👥 <b>Управление рангами — {html.escape(clan.name)}</b>\n\nВыберите участника для изменения ранга:",
        builder.as_markup(),
    )


@router.callback_query(F.data.startswith("clan_rank_menu:"))
async def cb_rank_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    target_id = int(cb.data.split(":")[1])
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan or clan.owner_id != user.id:
        await cb.answer("Только владелец клана может управлять рангами", show_alert=True)
        return

    target = await session.scalar(select(User).where(User.id == target_id))
    if not target:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    member = await session.scalar(
        select(ClanMember).where(
            ClanMember.clan_id == clan.id,
            ClanMember.user_id == target_id,
        )
    )
    if not member:
        await cb.answer("Игрок не в вашем клане", show_alert=True)
        return

    current_rank = RANK_LABELS.get(member.rank, member.rank)

    builder = InlineKeyboardBuilder()
    for rank_key, rank_name in [("deputy", "🛡 Заместитель"), ("captain", "⚔️ Капитан"), ("member", "👤 Участник")]:
        if member.rank != rank_key:
            builder.row(InlineKeyboardButton(
                text=f"Назначить {rank_name}",
                callback_data=f"clan_set_rank:{target_id}:{rank_key}",
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_manage_ranks"))

    await _reply(
        cb,
        f"👤 <b>{html.escape(target.full_name)}</b>\nТекущий ранг: {current_rank}\n\nВыберите новый ранг:",
        builder.as_markup(),
    )


@router.callback_query(F.data.startswith("clan_set_rank:"))
async def cb_set_rank(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    target_id = int(parts[1])
    new_rank = parts[2]

    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    result = await clan_service.set_member_rank(session, clan, user.id, target_id, new_rank)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    await session.commit()
    rank_name = RANK_LABELS.get(new_rank, new_rank)
    await cb.answer(f"✅ Ранг изменён на {rank_name}", show_alert=True)
    await cb_manage_ranks(cb, session, user)


# ── Зал Славы ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "region_hall_of_fame")
async def cb_hall_of_fame(cb: CallbackQuery, session: AsyncSession, user: User):
    # Топ кланов по победам в войнах за регионы
    wins_result = await session.execute(
        select(KoreanRegionWar.winner_clan_id, func.count(KoreanRegionWar.id).label("wins"))
        .where(
            KoreanRegionWar.is_finished == True,
            KoreanRegionWar.winner_clan_id.isnot(None),
        )
        .group_by(KoreanRegionWar.winner_clan_id)
        .order_by(func.count(KoreanRegionWar.id).desc())
        .limit(10)
    )
    clan_wins = wins_result.all()

    # Batch load clans for top winners
    top_clan_ids = [row.winner_clan_id for row in clan_wins]
    if top_clan_ids:
        clans_map = {c.id: c for c in (await session.execute(
            select(Clan).where(Clan.id.in_(top_clan_ids))
        )).scalars().all()}
    else:
        clans_map = {}

    lines = ["🏆 <b>Зал Славы — Лучшие кланы</b>\n"]
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    if clan_wins:
        for i, row in enumerate(clan_wins):
            c = clans_map.get(row.winner_clan_id)
            name = html.escape(c.name) if c else "?"
            lines.append(f"{medals[i]} <b>{name}</b> — {row.wins} побед")
    else:
        lines.append("Пока ни одного завершённого сражения.")

    # Последние захваченные регионы — batch load regions + clans
    recent = await session.execute(
        select(KoreanRegionWar)
        .where(KoreanRegionWar.is_finished == True, KoreanRegionWar.winner_clan_id.isnot(None))
        .order_by(KoreanRegionWar.ends_at.desc())
        .limit(5)
    )
    recent_wars = recent.scalars().all()
    if recent_wars:
        r_ids = [w.region_id for w in recent_wars]
        w_clan_ids = [w.winner_clan_id for w in recent_wars if w.winner_clan_id]
        regions_map = {r.id: r for r in (await session.execute(
            select(KoreanRegion).where(KoreanRegion.id.in_(r_ids))
        )).scalars().all()}
        recent_clans = {c.id: c for c in (await session.execute(
            select(Clan).where(Clan.id.in_(w_clan_ids))
        )).scalars().all()}

        lines.append("\n📜 <b>Последние захваты:</b>")
        for w in recent_wars:
            reg = regions_map.get(w.region_id)
            win = recent_clans.get(w.winner_clan_id)
            r_name = f"{reg.emoji} {reg.name}" if reg else "?"
            c_name = html.escape(win.name) if win else "?"
            lines.append(f"• {r_name} → <b>{c_name}</b>")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚡ Топ активных игроков", callback_data="region_top_active"))
    builder.row(InlineKeyboardButton(text="◀️ Карта", callback_data="clan_regions_map"))

    await _reply(cb, "\n".join(lines), builder.as_markup())


@router.callback_query(F.data == "region_top_active")
async def cb_top_active(cb: CallbackQuery, session: AsyncSession, user: User):
    score_expr = (
        func.least(KoreanRegionActivity.train_count, 10) * 1
        + func.least(KoreanRegionActivity.attack_gang_count, 5) * 2
        + func.least(KoreanRegionActivity.attack_king_count, 5) * 3
        + func.least(KoreanRegionActivity.attack_fist_count, 3) * 4
        + func.least(KoreanRegionActivity.spend_count, 10) * 1
        + func.least(KoreanRegionActivity.raid_count, 5) * 3
        + func.least(KoreanRegionActivity.recruit_count, 10) * 1
    )
    top_result = await session.execute(
        select(KoreanRegionActivity.user_id, func.sum(score_expr).label("total"))
        .group_by(KoreanRegionActivity.user_id)
        .order_by(func.sum(score_expr).desc())
        .limit(15)
    )
    top_players = top_result.all()

    # Batch load users, clan members, clans (3 queries instead of 3N)
    player_ids = [row.user_id for row in top_players]
    if player_ids:
        users_map = {u.id: u for u in (await session.execute(
            select(User.id, User.full_name).where(User.id.in_(player_ids))
        )).all()}
        members_rows = (await session.execute(
            select(ClanMember.user_id, ClanMember.clan_id).where(ClanMember.user_id.in_(player_ids))
        )).all()
        member_clan_map = {m.user_id: m.clan_id for m in members_rows}
        clan_ids = list(set(member_clan_map.values()))
        clans_map = {c.id: c for c in (await session.execute(
            select(Clan.id, Clan.name).where(Clan.id.in_(clan_ids))
        )).all()} if clan_ids else {}
    else:
        users_map, member_clan_map, clans_map = {}, {}, {}

    lines = ["⚡ <b>Топ активных игроков (все войны)</b>\n"]
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 12
    if top_players:
        for i, row in enumerate(top_players):
            u = users_map.get(row.user_id)
            name = html.escape(u.full_name) if u else f"#{row.user_id}"
            clan_id = member_clan_map.get(row.user_id)
            c = clans_map.get(clan_id) if clan_id else None
            clan_str = f" [{html.escape(c.name)}]" if c else ""
            lines.append(f"{medals[i]} <b>{name}</b>{clan_str} — {int(row.total)} очков")
    else:
        lines.append("Активность пока не зафиксирована.")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏆 Топ кланов", callback_data="region_hall_of_fame"))
    builder.row(InlineKeyboardButton(text="◀️ Карта", callback_data="clan_regions_map"))

    await _reply(cb, "\n".join(lines), builder.as_markup())
