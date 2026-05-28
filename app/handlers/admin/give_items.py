"""Выдача игровых предметов: статисты, карточки, пыль, города, абсолютные карты, duel CD."""
import html
from collections import defaultdict
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.user import User
from app.models.character import UserCharacter
from app.services.admin_service import admin_service
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_power, fmt_num
from app.handlers.admin._common import is_admin, AdminFSM, _show_user_card

router = Router()


# ── Карточки: подменю ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_cards_menu:"))
async def cb_adm_cards_menu(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Выдать карточку", callback_data=f"adm_card_give_rank:{tg_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Забрать карточку", callback_data=f"adm_card_take_rank:{tg_id}"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_user:{tg_id}"))
    try:
        await cb.message.edit_text(
            "🃏 <b>Управление карточками</b>\n\nЧто сделать?",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


# ── Карточки: выдача — выбор ранга ────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_card_give_rank:"))
async def cb_adm_card_give_rank(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    from app.data.characters import CHARACTER_RANKS, RANK_EMOJI
    builder = InlineKeyboardBuilder()
    for rc in reversed(CHARACTER_RANKS):  # от сильнейших к слабым
        emoji = RANK_EMOJI.get(rc.rank, "❓")
        builder.row(InlineKeyboardButton(
            text=f"{emoji} {rc.label}",
            callback_data=f"adm_card_give_chars:{tg_id}:{rc.rank}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_cards_menu:{tg_id}"))
    try:
        await cb.message.edit_text(
            "✅ <b>Выдать карточку</b>\n\nВыберите ранг:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


# ── Карточки: выдача — выбор персонажа ────────────────────────────────────

@router.callback_query(F.data.startswith("adm_card_give_chars:"))
async def cb_adm_card_give_chars(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, rank = parts[1], parts[2]
    from app.data.characters import CHARACTERS, RANK_EMOJI
    # Use global index to keep callback_data short (avoid 64-byte Telegram limit)
    emoji = RANK_EMOJI.get(rank, "❓")
    builder = InlineKeyboardBuilder()
    for idx, c in enumerate(CHARACTERS):
        if c["rank"] != rank:
            continue
        builder.row(InlineKeyboardButton(
            text=f"{c['name']}",
            callback_data=f"adm_cgl:{tg_id}:{idx}",
        ))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_card_give_rank:{tg_id}"))
    try:
        await cb.message.edit_text(
            f"✅ <b>Выдать карточку</b>\n{emoji} Ранг: {rank}\n\nВыберите персонажа:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


# ── Карточки: выдача — выбор уровня ───────────────────────────────────────

@router.callback_query(F.data.startswith("adm_card_give_level:"))
async def cb_adm_card_give_level(cb: CallbackQuery, user: User):
    """Legacy handler — kept for backward compat but now unused."""
    await cb.answer("Используйте новое меню", show_alert=True)


@router.callback_query(F.data.startswith("adm_cgl:"))
async def cb_adm_cgl(cb: CallbackQuery, user: User):
    """adm_cgl:{tg_id}:{char_global_idx} — choose level for card give."""
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, char_idx = parts[1], int(parts[2])
    from app.data.characters import CHARACTERS
    from app.constants.cards import LEVEL_LABELS, LEVEL_MULTIPLIERS
    if char_idx >= len(CHARACTERS):
        await cb.answer("Персонаж не найден", show_alert=True)
        return
    char_data = CHARACTERS[char_idx]
    builder = InlineKeyboardBuilder()
    for lvl, lbl in LEVEL_LABELS.items():
        power = int(char_data["power"] * LEVEL_MULTIPLIERS[lvl])
        builder.row(InlineKeyboardButton(
            text=f"{lbl} — {fmt_power(power)} мощи",
            callback_data=f"adm_cgq:{tg_id}:{char_idx}:{lvl}",
        ))
    rank = char_data["rank"]
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_card_give_chars:{tg_id}:{rank}"))
    try:
        await cb.message.edit_text(
            f"✅ <b>Выдать карточку</b>\n👤 {char_data['name']}\n\nВыберите уровень:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


# ── Карточки: выдача — ввод количества ────────────────────────────────────

@router.callback_query(F.data.startswith("adm_card_give_qty:"))
async def cb_adm_card_give_qty(cb: CallbackQuery, user: User, state: FSMContext):
    """Legacy handler — kept for backward compat."""
    await cb.answer("Используйте новое меню", show_alert=True)


@router.callback_query(F.data.startswith("adm_cgq:"))
async def cb_adm_cgq(cb: CallbackQuery, user: User, state: FSMContext):
    """adm_cgq:{tg_id}:{char_global_idx}:{level} — enter qty for card give."""
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, char_idx, level = parts[1], int(parts[2]), int(parts[3])
    from app.data.characters import CHARACTERS
    if char_idx >= len(CHARACTERS):
        await cb.answer("Персонаж не найден", show_alert=True)
        return
    char_data = CHARACTERS[char_idx]
    await state.set_state(AdminFSM.waiting_card_qty)
    await state.update_data(card_give_tg_id=int(tg_id), card_give_char_idx=char_idx, card_give_level=level)
    from app.constants.cards import LEVEL_LABELS
    lbl = LEVEL_LABELS.get(level, f"Ур.{level}")
    try:
        await cb.message.edit_text(
            f"✅ <b>Выдать карточку</b>\n👤 {char_data['name']} [{lbl}]\n\nВведите количество (1-100):",
            reply_markup=back_kb(f"adm_cards_menu:{tg_id}"), parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_card_qty)
async def msg_adm_card_give_qty(message: Message, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    data = await state.get_data()
    await state.clear()
    try:
        qty = int(message.text.strip())
        assert 1 <= qty <= 100
    except (ValueError, AssertionError):
        await message.answer("Введите число от 1 до 100")
        return
    tg_id = data["card_give_tg_id"]
    level = data["card_give_level"]
    # Support both old (name) and new (idx) flows
    from app.data.characters import CHARACTERS
    char_idx = data.get("card_give_char_idx")
    char_name = data.get("card_give_name")
    if char_idx is not None:
        char_data = CHARACTERS[char_idx] if char_idx < len(CHARACTERS) else None
    else:
        char_data = next((c for c in CHARACTERS if c["name"] == char_name), None)
    if not char_data:
        await message.answer("❌ Персонаж не найден")
        return
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await message.answer("❌ Игрок не найден")
        return
    from app.constants.cards import LEVEL_MULTIPLIERS, LEVEL_LABELS
    base_power = char_data["power"]
    eff_power = int(base_power * LEVEL_MULTIPLIERS[level])
    for _ in range(qty):
        session.add(UserCharacter(
            user_id=found.id, character_id=char_data["name"], rank=char_data["rank"],
            base_power=base_power, power=eff_power, level=level,
        ))
    await session.flush()
    from app.repositories.squad_repo import squad_repo
    await squad_repo.update_user_combat_power(session, found)
    await session.commit()
    lbl = LEVEL_LABELS.get(level, f"Ур.{level}")
    await message.answer(
        f"✅ Выдано {qty} × {char_data['name']} [{lbl}] игроку {html.escape(found.full_name)}",
        parse_mode="HTML",
    )
    await _show_user_card(message, session, found)


# ── Карточки: забрать — выбор ранга ──────────────────────────────────────

@router.callback_query(F.data.startswith("adm_card_take_rank:"))
async def cb_adm_card_take_rank(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    # Получить уникальные ранги карточек у игрока
    rows = (await session.execute(
        select(UserCharacter.rank, func.count(UserCharacter.id))
        .where(UserCharacter.user_id == found.id)
        .group_by(UserCharacter.rank)
    )).all()
    if not rows:
        await cb.answer("У игрока нет карточек", show_alert=True)
        return
    from app.data.characters import RANK_EMOJI, RANK_CONFIG_MAP
    rank_order = ["perfection","absolute","peak","legend","new_legend","gen_zero","strong_king","king","boss","member"]
    rank_counts = {r: c for r, c in rows}
    builder = InlineKeyboardBuilder()
    for rank in rank_order:
        if rank not in rank_counts:
            continue
        emoji = RANK_EMOJI.get(rank, "❓")
        cfg = RANK_CONFIG_MAP.get(rank)
        label = cfg.label if cfg else rank
        cnt = rank_counts[rank]
        builder.row(InlineKeyboardButton(
            text=f"{emoji} {label} ×{cnt}",
            callback_data=f"adm_card_take_chars:{tg_id}:{rank}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_cards_menu:{tg_id}"))
    try:
        await cb.message.edit_text(
            f"❌ <b>Забрать карточку</b> — {html.escape(found.full_name)}\n\nВыберите ранг:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


# ── Карточки: забрать — выбор персонажа ──────────────────────────────────

@router.callback_query(F.data.startswith("adm_card_take_chars:"))
async def cb_adm_card_take_chars(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, rank = int(parts[1]), parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    rows = (await session.execute(
        select(UserCharacter.character_id, UserCharacter.level, func.count(UserCharacter.id))
        .where(UserCharacter.user_id == found.id, UserCharacter.rank == rank)
        .group_by(UserCharacter.character_id, UserCharacter.level)
        .order_by(UserCharacter.character_id)
    )).all()
    if not rows:
        await cb.answer("Нет карточек этого ранга", show_alert=True)
        return
    from app.constants.cards import LEVEL_LABELS
    from app.data.characters import RANK_EMOJI
    emoji = RANK_EMOJI.get(rank, "❓")
    builder = InlineKeyboardBuilder()
    for char_name, level, cnt in rows:
        lbl = LEVEL_LABELS.get(level, f"Ур.{level}")
        builder.row(InlineKeyboardButton(
            text=f"{char_name} [{lbl}] ×{cnt}",
            callback_data=f"adm_card_take_confirm:{tg_id}:{rank}:{char_name}:{level}:{cnt}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_card_take_rank:{tg_id}"))
    try:
        await cb.message.edit_text(
            f"❌ <b>Забрать карточку</b>\n{emoji} Ранг: {rank}\n\nВыберите карточку:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


# ── Карточки: забрать — ввод количества ──────────────────────────────────

@router.callback_query(F.data.startswith("adm_card_take_confirm:"))
async def cb_adm_card_take_confirm(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":", 6)
    tg_id, rank, char_name, level, max_cnt = parts[1], parts[2], parts[3], int(parts[4]), int(parts[5])
    from app.constants.cards import LEVEL_LABELS
    lbl = LEVEL_LABELS.get(level, f"Ур.{level}")
    await state.set_state(AdminFSM.waiting_card_take_qty)
    await state.update_data(
        card_take_tg_id=int(tg_id), card_take_rank=rank,
        card_take_name=char_name, card_take_level=level, card_take_max=max_cnt,
    )
    try:
        await cb.message.edit_text(
            f"❌ <b>Забрать карточку</b>\n"
            f"👤 {char_name} [{lbl}]\n"
            f"📦 У игрока: {max_cnt} шт.\n\n"
            f"Введите количество для удаления (1-{max_cnt}):",
            reply_markup=back_kb(f"adm_card_take_chars:{tg_id}:{rank}"), parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_card_take_qty)
async def msg_adm_card_take_qty(message: Message, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    data = await state.get_data()
    await state.clear()
    max_cnt = data["card_take_max"]
    try:
        qty = int(message.text.strip())
        assert 1 <= qty <= max_cnt
    except (ValueError, AssertionError):
        await message.answer(f"Введите число от 1 до {max_cnt}")
        return
    tg_id = data["card_take_tg_id"]
    char_name = data["card_take_name"]
    level = data["card_take_level"]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await message.answer("❌ Игрок не найден")
        return
    cards = (await session.execute(
        select(UserCharacter)
        .where(
            UserCharacter.user_id == found.id,
            UserCharacter.character_id == char_name,
            UserCharacter.level == level,
        )
        .limit(qty)
    )).scalars().all()
    removed = 0
    for c in cards[:qty]:
        await session.delete(c)
        removed += 1
    await session.flush()
    from app.repositories.squad_repo import squad_repo
    await squad_repo.update_user_combat_power(session, found)
    await session.commit()
    from app.constants.cards import LEVEL_LABELS
    lbl = LEVEL_LABELS.get(level, f"Ур.{level}")
    await message.answer(
        f"✅ Удалено {removed} × {char_name} [{lbl}] у {html.escape(found.full_name)}",
        parse_mode="HTML",
    )
    await _show_user_card(message, session, found)


# ── Статисты ─────────────────────────────────────────────────────────────────

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
            callback_data=f"adm_give_squad:{tg_id}:{rank_cfg.rank}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_user:{tg_id}"))
    try:
        await cb.message.edit_text("👥 Выберите ранг статиста для выдачи:", reply_markup=builder.as_markup())
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


# ── Абсолютные карты ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_give_abs:"))
async def cb_adm_give_abs(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    from app.data.characters import CHARACTERS
    absolutes = [c for c in CHARACTERS if c["rank"] == "absolute"]
    builder = InlineKeyboardBuilder()
    for c in absolutes:
        builder.row(InlineKeyboardButton(
            text=f"🌟 {c['name']} ({c['power']:,} мощи)",
            callback_data=f"adm_pick_abs:{tg_id}:{c['name']}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_user:{tg_id}"))
    try:
        await cb.message.edit_text(
            "🌟 <b>Выдать абсолютную карту</b>\n\nВыберите персонажа:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_pick_abs:"))
async def cb_adm_pick_abs(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":", 2)
    tg_id, char_name = parts[1], parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    result = await admin_service.give_absolute_character(session, found, char_name)
    if result["ok"]:
        c = result["character"]
        await cb.answer(f"✅ {c['name']} выдан! (+{c['power']:,} мощи)", show_alert=True)
        await _show_user_card(cb.message, session, found)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data.startswith("adm_take_abs:"))
async def cb_adm_take_abs(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🗑 Да, удалить все абсолютные карты",
        callback_data=f"adm_take_abs_do:{tg_id}",
    ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"adm_user:{tg_id}"))
    try:
        await cb.message.edit_text(
            "⚠️ <b>Удалить все абсолютные карты игрока?</b>\n\nПодтвердить?",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_take_abs_do:"))
async def cb_adm_take_abs_do(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    result = await admin_service.take_absolute_characters(session, found)
    await cb.answer(f"✅ Удалено {result['removed']} абс. карт", show_alert=True)
    await _show_user_card(cb.message, session, found)


# ── Города ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_give_city:"))
async def cb_adm_give_city(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    result = await admin_service.give_king_city(session, found)
    if result["ok"]:
        await cb.answer(
            f"✅ Выдан город «{result['city_name']}»\nГородов: {result['cities_count']}",
            show_alert=True,
        )
        await _show_user_card(cb.message, session, found)
    else:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)


@router.callback_query(F.data.startswith("adm_take_cities:"))
async def cb_adm_take_cities(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🏙 Да, забрать все города",
        callback_data=f"adm_take_cities_do:{tg_id}",
    ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"adm_user:{tg_id}"))
    try:
        await cb.message.edit_text(
            "⚠️ <b>Забрать все города игрока?</b>\n\n"
            "Все районы будут освобождены, счётчики городов обнулятся.\n\nПодтвердить?",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_take_cities_do:"))
async def cb_adm_take_cities_do(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    result = await admin_service.take_all_cities(session, found)
    await cb.answer(
        f"✅ Освобождено {result['removed']} районов, города обнулены", show_alert=True
    )
    await _show_user_card(cb.message, session, found)


# ── Карточки / пыль / duel CD ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_give_card:"))
async def cb_adm_give_card(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    await state.set_state(AdminFSM.waiting_card_char)
    await state.update_data(card_target_tg_id=tg_id)

    from app.data.characters import CHARACTERS, RANK_CONFIG_MAP, RANK_EMOJI
    from collections import defaultdict
    by_rank: dict[str, list] = defaultdict(list)
    for c in CHARACTERS:
        by_rank[c["rank"]].append(c["name"])

    rank_order = ["perfection", "absolute", "peak", "legend", "new_legend",
                  "gen_zero", "strong_king", "king", "boss", "member"]
    lines = ["🃏 <b>Выдать карточку</b>\n", "Введи <b>точное имя</b> персонажа:\n"]
    for rank in rank_order:
        if rank not in by_rank:
            continue
        emoji = RANK_EMOJI.get(rank, "❓")
        cfg = RANK_CONFIG_MAP.get(rank)
        label = cfg.label if cfg else rank
        sample = ", ".join(by_rank[rank][:2])
        lines.append(f"{emoji} {label}: {sample}...")
    try:
        await cb.message.edit_text(
            "\n".join(lines), reply_markup=back_kb("admin_main"), parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_card_char)
async def msg_admin_card_char(message: Message, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    char_name = message.text.strip()
    from app.data.characters import CHARACTERS
    char_data = next((c for c in CHARACTERS if c["name"].lower() == char_name.lower()), None)
    if not char_data:
        matches = [c for c in CHARACTERS if char_name.lower() in c["name"].lower()]
        if matches:
            names = "\n".join(f"• {c['name']}" for c in matches[:10])
            await message.answer(
                f"❌ Точное совпадение не найдено.\nПохожие:\n{names}\n\nВведи точное имя:",
                reply_markup=back_kb("admin_main"), parse_mode="HTML",
            )
        else:
            await message.answer("❌ Персонаж не найден. Введи точное имя из списка.", reply_markup=back_kb("admin_main"))
        return
    await state.update_data(card_char_name=char_data["name"], card_char_rank=char_data["rank"],
                            card_char_power=char_data["power"])
    await state.set_state(AdminFSM.waiting_card_level)
    from app.constants.cards import LEVEL_LABELS, LEVEL_MULTIPLIERS
    lvl_lines = [f"  {lbl} → {fmt_power(int(char_data['power'] * LEVEL_MULTIPLIERS[lvl]))} мощи"
                 for lvl, lbl in LEVEL_LABELS.items()]
    await message.answer(
        f"✅ Персонаж: <b>{char_data['name']}</b>\n\nМощь по уровням:\n"
        + "\n".join(lvl_lines) + "\n\nВведи уровень карточки (0-3):",
        reply_markup=back_kb("admin_main"), parse_mode="HTML",
    )


@router.message(AdminFSM.waiting_card_level)
async def msg_admin_card_level(message: Message, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    try:
        level = int(message.text.strip())
        assert 0 <= level <= 3
    except (ValueError, AssertionError):
        await message.answer("❌ Введи уровень от 0 до 3:")
        return
    data = await state.get_data()
    await state.clear()
    target_tg_id = data["card_target_tg_id"]
    char_name = data["card_char_name"]
    char_rank = data["card_char_rank"]
    base_power = data["card_char_power"]
    found = await admin_service.find_user(session, str(target_tg_id))
    if not found:
        await message.answer("❌ Игрок не найден", reply_markup=back_kb("admin_main"))
        return
    from app.models.character import UserCharacter
    from app.constants.cards import LEVEL_MULTIPLIERS, LEVEL_LABELS
    eff_power = int(base_power * LEVEL_MULTIPLIERS[level])
    session.add(UserCharacter(
        user_id=found.id, character_id=char_name, rank=char_rank,
        base_power=base_power, power=eff_power, level=level,
    ))
    await session.flush()
    from app.repositories.squad_repo import squad_repo
    await squad_repo.update_user_combat_power(session, found)
    await session.commit()
    lvl_lbl = LEVEL_LABELS.get(level, f"Ур.{level}")
    await message.answer(
        f"✅ Карточка выдана!\n\n👤 {html.escape(found.full_name)}\n"
        f"🃏 {char_name} [{lvl_lbl}]\n💪 Мощь: {fmt_power(eff_power)}",
        reply_markup=back_kb("admin_main"), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_give_dust:"))
async def cb_adm_give_dust(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    await state.set_state(AdminFSM.waiting_dust_amount)
    await state.update_data(dust_target_tg_id=tg_id)
    try:
        await cb.message.edit_text(
            "💎 <b>Выдать пыль</b>\n\nВведи количество пыли (1-9999999):",
            reply_markup=back_kb("admin_main"), parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_dust_amount)
async def msg_admin_dust_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    try:
        amount = int(message.text.strip())
        assert 1 <= amount <= 9_999_999
    except (ValueError, AssertionError):
        await message.answer("❌ Введи число от 1 до 9999999:")
        return
    data = await state.get_data()
    await state.clear()
    found = await admin_service.find_user(session, str(data["dust_target_tg_id"]))
    if not found:
        await message.answer("❌ Игрок не найден", reply_markup=back_kb("admin_main"))
        return
    found.card_dust = (found.card_dust or 0) + amount
    await session.commit()
    await message.answer(
        f"✅ Пыль выдана!\n\n👤 {html.escape(found.full_name)}\n"
        f"💎 +{fmt_num(amount)} пыли\nИтого: {fmt_num(found.card_dust)}",
        reply_markup=back_kb("admin_main"), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_toggle_duel_cd:"))
async def cb_adm_toggle_duel_cd(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    found.donat_duel_cd = not getattr(found, "donat_duel_cd", False)
    await session.commit()
    state_str = "✅ включён" if found.donat_duel_cd else "❌ отключён"
    await cb.answer(f"Дуэль -20% КД: {state_str}", show_alert=True)
    await _show_user_card(cb.message, session, found)
