from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.clan import ClanMember
from app.services.clan import clan_service
from app.utils.formatters import fmt_num
import html

router = Router()


class ExchangeFSM(StatesGroup):
    waiting_amount = State()


RESOURCES = [
    ("coins",               "💰 NHCoin"),
    ("tickets",             "🎟 Тикеты"),
    ("card_dust",           "🌫 Пыль карт"),
    ("mastery_points",      "⭐ Очки мастерства"),
    ("ui_fragments",        "🔮 Фрагменты УИ"),
    ("alchemy_fragments",   "🧪 Фрагменты алхимии"),
    ("path_fragments",      "🔷 Фрагменты Пути"),
    ("path_points",         "🔷 Очки пути"),
    ("business_fragments",  "🏭 Фрагменты бизнеса"),
    ("war_points",          "⚔️ Очки войны"),
    ("squad",               "👥 Статисты"),
    ("character",           "🎴 Персонажи"),
]

RESOURCE_FIELDS = {
    "coins":               "nh_coins",
    "tickets":             "tickets",
    "card_dust":           "card_dust",
    "mastery_points":      "mastery_points",
    "ui_fragments":        "ui_fragments",
    "alchemy_fragments":   "alchemy_fragments",
    "path_fragments":      "path_fragments",
    "path_points":         "skill_path_points",
    "business_fragments":  "business_fragments",
    "war_points":          "war_points",
}

RANK_ORDER = ["absolute", "peak", "legend", "new_legend", "gen_zero", "strong_king", "king", "boss", "member"]


# ── Список участников клана ──────────────────────────────────────────────────

@router.callback_query(F.data == "clan_exchange")
async def cb_clan_exchange(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    result = await session.execute(
        select(User)
        .join(ClanMember, ClanMember.user_id == User.id)
        .where(ClanMember.clan_id == clan.id, User.id != user.id)
    )
    targets = result.scalars().all()

    if not targets:
        await cb.answer("В клане нет других участников", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for target in targets:
        builder.row(InlineKeyboardButton(
            text=f"👤 {html.escape(target.full_name)} | 💪{fmt_num(target.combat_power)}",
            callback_data=f"clan_exch_target:{target.id}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))
    try:
        await cb.message.edit_text(
            "🔄 <b>Обмен ресурсами</b>\n\nВыбери участника:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


# ── Выбор ресурса с фильтрацией (пустые ресурсы скрываются) ─────────────────

@router.callback_query(F.data.startswith("clan_exch_target:"))
async def cb_clan_exch_target(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    target_id = int(cb.data.split(":")[1])
    target = await session.scalar(select(User).where(User.id == target_id))
    if not target:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    from app.models.squad_member import SquadMember
    from app.models.character import UserCharacter

    squad_count = await session.scalar(
        select(func.count(SquadMember.id)).where(SquadMember.user_id == user.id)
    )
    char_count = await session.scalar(
        select(func.count(UserCharacter.id)).where(UserCharacter.user_id == user.id)
    )

    await state.update_data(target_id=target_id)

    builder = InlineKeyboardBuilder()
    for res_id, res_name in RESOURCES:
        if res_id == "squad":
            if not squad_count:
                continue
            text = f"{res_name}: {fmt_num(squad_count)}"
        elif res_id == "character":
            if not char_count:
                continue
            text = f"{res_name}: {char_count}"
        else:
            field = RESOURCE_FIELDS.get(res_id)
            val = getattr(user, field, 0) if field else 0
            text = f"{res_name}: {fmt_num(val)}"
        builder.row(InlineKeyboardButton(text=text, callback_data=f"clan_exch_res:{target_id}:{res_id}"))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_exchange"))
    try:
        await cb.message.edit_text(
            f"🔄 Обмен с <b>{html.escape(target.full_name)}</b>\n\nВыбери ресурс:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


# ── Маршрутизация по типу ресурса ────────────────────────────────────────────

@router.callback_query(F.data.startswith("clan_exch_res:"))
async def cb_clan_exch_res(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    parts = cb.data.split(":")
    target_id = int(parts[1])
    resource = parts[2]

    if resource == "squad":
        from app.data.squad import RANKS_BY_ID
        from app.models.squad_member import SquadMember

        result = await session.execute(
            select(SquadMember.rank, func.count(SquadMember.id).label("cnt"))
            .where(SquadMember.user_id == user.id)
            .group_by(SquadMember.rank)
        )
        rank_counts = {row.rank: row.cnt for row in result.all()}

        builder = InlineKeyboardBuilder()
        for rank, count in rank_counts.items():
            cfg = RANKS_BY_ID.get(rank)
            emoji = cfg.emoji if cfg else "•"
            builder.row(InlineKeyboardButton(
                text=f"{emoji} {rank} × {count}",
                callback_data=f"clan_exch_squad_rank:{target_id}:{rank}",
            ))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"clan_exch_target:{target_id}"))
        try:
            await cb.message.edit_text(
                "👥 <b>Выбери ранг статистов для передачи:</b>",
                reply_markup=builder.as_markup(), parse_mode="HTML",
            )
        except Exception:
            pass
        return

    if resource == "character":
        from app.models.character import UserCharacter
        from app.data.characters import RANK_EMOJI, RANK_CONFIG_MAP

        result = await session.execute(
            select(UserCharacter.rank, func.count(UserCharacter.id).label("cnt"))
            .where(UserCharacter.user_id == user.id)
            .group_by(UserCharacter.rank)
        )
        rank_counts = {row.rank: row.cnt for row in result.all()}

        builder = InlineKeyboardBuilder()
        for rank in RANK_ORDER:
            if rank not in rank_counts:
                continue
            emoji = RANK_EMOJI.get(rank, "•")
            cfg = RANK_CONFIG_MAP.get(rank)
            label = cfg.label if cfg else rank
            builder.row(InlineKeyboardButton(
                text=f"{emoji} {label} × {rank_counts[rank]}",
                callback_data=f"clan_exch_char_rank:{target_id}:{rank}",
            ))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"clan_exch_target:{target_id}"))
        try:
            await cb.message.edit_text(
                "🎴 <b>Выбери ранг персонажа для передачи:</b>",
                reply_markup=builder.as_markup(), parse_mode="HTML",
            )
        except Exception:
            pass
        return

    # Обычные ресурсы — запрос количества
    await state.set_state(ExchangeFSM.waiting_amount)
    await state.update_data(target_id=target_id, resource=resource)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"clan_exch_target:{target_id}"))
    try:
        await cb.message.edit_text("🔄 Введите количество для передачи:", reply_markup=cancel_kb.as_markup())
    except Exception:
        pass


# ── Статисты: выбор ранга → количество или всё сразу ─────────────────────────

@router.callback_query(F.data.startswith("clan_exch_squad_rank:"))
async def cb_clan_exch_squad_rank(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    parts = cb.data.split(":")
    target_id = int(parts[1])
    rank = parts[2]

    from app.models.squad_member import SquadMember
    count = await session.scalar(
        select(func.count(SquadMember.id)).where(SquadMember.user_id == user.id, SquadMember.rank == rank)
    )

    await state.set_state(ExchangeFSM.waiting_amount)
    await state.update_data(target_id=target_id, resource="squad", meta={"rank": rank})

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"📦 Передать всех ({rank}) — {count} шт.",
        callback_data=f"clan_exch_squad_all:{target_id}:{rank}",
    ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"clan_exch_res:{target_id}:squad"))
    try:
        await cb.message.edit_text(
            f"👥 Передача статистов ранга <b>{rank}</b>\nДоступно: <b>{count}</b>\n\nВведите количество или передайте всех:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_exch_squad_all:"))
async def cb_clan_exch_squad_all(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    parts = cb.data.split(":")
    target_id = int(parts[1])
    rank = parts[2]

    await state.clear()
    target = await session.scalar(select(User).where(User.id == target_id))
    if not target:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    result = await clan_service.exchange_resource(session, user, target, "squad_all", 0, meta={"rank": rank})
    if result["ok"]:
        await cb.answer(f"✅ Все статисты ранга {rank} переданы {html.escape(target.full_name)}!", show_alert=True)
    else:
        await cb.answer(result["reason"], show_alert=True)


# ── Персонажи: список уникальных персонажей в категории ─────────────────────

@router.callback_query(F.data.startswith("clan_exch_char_rank:"))
async def cb_clan_exch_char_rank(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    parts = cb.data.split(":")
    target_id = int(parts[1])
    rank = parts[2]

    from app.models.character import UserCharacter
    from app.data.characters import RANK_EMOJI, RANK_CONFIG_MAP

    result = await session.execute(
        select(
            UserCharacter.character_id,
            func.count(UserCharacter.id).label("cnt"),
            func.sum(UserCharacter.power).label("total_power"),
            func.avg(UserCharacter.level).label("avg_level"),
        )
        .where(UserCharacter.user_id == user.id, UserCharacter.rank == rank)
        .group_by(UserCharacter.character_id)
        .order_by(func.sum(UserCharacter.power).desc())
    )
    rows = result.all()

    if not rows:
        await cb.answer("Нет персонажей этого ранга", show_alert=True)
        return

    total_count = sum(r.cnt for r in rows)
    char_names = [r.character_id for r in rows]

    # Сохраняем список имён для доступа по индексу из коллбэков
    await state.clear()
    await state.update_data(char_names=char_names, current_rank=rank, current_target_id=target_id)

    emoji = RANK_EMOJI.get(rank, "🎴")
    cfg = RANK_CONFIG_MAP.get(rank)
    rank_label = cfg.label if cfg else rank

    from app.constants.cards import LEVEL_LABELS
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"📦 Передать всю категорию — {total_count} шт.",
        callback_data=f"clan_exch_char_all:{target_id}:{rank}",
    ))
    for idx, row in enumerate(rows):
        avg_lvl = int(row.avg_level or 0)
        lvl_lbl = LEVEL_LABELS.get(avg_lvl, f"Ур.{avg_lvl}")
        builder.row(InlineKeyboardButton(
            text=f"{emoji} {row.character_id} × {row.cnt} | {lvl_lbl} | {fmt_num(row.total_power)} мощи",
            callback_data=f"clan_exch_char_name:{target_id}:{idx}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"clan_exch_res:{target_id}:character"))
    try:
        await cb.message.edit_text(
            f"🎴 <b>{rank_label}</b> — {total_count} шт.\n\nВыбери персонажа или передай всю категорию:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


# ── Персонажи: передать всю категорию (ранг) сразу ──────────────────────────

@router.callback_query(F.data.startswith("clan_exch_char_all:"))
async def cb_clan_exch_char_all(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    parts = cb.data.split(":")
    target_id = int(parts[1])
    rank = parts[2]

    await state.clear()
    target = await session.scalar(select(User).where(User.id == target_id))
    if not target:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    result = await clan_service.exchange_resource(session, user, target, "character_rank", 0, meta={"rank": rank})
    if result["ok"]:
        await cb.answer(
            f"✅ Все персонажи ранга {rank} переданы {html.escape(target.full_name)}!",
            show_alert=True,
        )
    else:
        await cb.answer(result["reason"], show_alert=True)


# ── Персонажи: выбор конкретного персонажа → количество ─────────────────────

@router.callback_query(F.data.startswith("clan_exch_char_name:"))
async def cb_clan_exch_char_name(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    parts = cb.data.split(":")
    target_id = int(parts[1])
    idx = int(parts[2])

    data = await state.get_data()
    char_names: list = data.get("char_names", [])
    rank = data.get("current_rank", "")

    if idx >= len(char_names):
        await cb.answer("Ошибка: персонаж не найден, вернитесь назад", show_alert=True)
        return

    char_name = char_names[idx]

    from app.models.character import UserCharacter
    count = await session.scalar(
        select(func.count(UserCharacter.id))
        .where(UserCharacter.user_id == user.id, UserCharacter.character_id == char_name)
    )

    await state.set_state(ExchangeFSM.waiting_amount)
    await state.update_data(target_id=target_id, resource="character_name", meta={"char_name": char_name})

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"📦 Передать всех — {count} шт.",
        callback_data=f"clan_exch_char_nameall:{target_id}",
    ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"clan_exch_char_rank:{target_id}:{rank}"))
    try:
        await cb.message.edit_text(
            f"🎴 <b>{html.escape(char_name)}</b>\nДоступно: <b>{count}</b>\n\nВведите количество для передачи:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


# ── Персонажи: передать всех конкретного персонажа ──────────────────────────

@router.callback_query(F.data.startswith("clan_exch_char_nameall:"))
async def cb_clan_exch_char_nameall(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    target_id = int(cb.data.split(":")[1])

    data = await state.get_data()
    meta = data.get("meta", {})
    char_name = meta.get("char_name")

    await state.clear()

    if not char_name:
        await cb.answer("Ошибка: вернитесь и выберите персонажа заново", show_alert=True)
        return

    target = await session.scalar(select(User).where(User.id == target_id))
    if not target:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    from app.models.character import UserCharacter
    count = await session.scalar(
        select(func.count(UserCharacter.id))
        .where(UserCharacter.user_id == user.id, UserCharacter.character_id == char_name)
    )
    if not count:
        await cb.answer("Нет персонажей для передачи", show_alert=True)
        return

    result = await clan_service.exchange_resource(
        session, user, target, "character_name", count, meta={"char_name": char_name}
    )
    if result["ok"]:
        await cb.answer(
            f"✅ {html.escape(char_name)} × {count} передан(ы) {html.escape(target.full_name)}!",
            show_alert=True,
        )
    else:
        await cb.answer(result["reason"], show_alert=True)


# ── Ввод количества (общий хэндлер для ресурсов и статистов) ────────────────

@router.message(ExchangeFSM.waiting_amount)
async def msg_exchange_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    target_id = data.get("target_id")
    resource = data.get("resource")
    meta = data.get("meta")

    target = await session.scalar(select(User).where(User.id == target_id))
    if not target:
        await message.answer("❌ Игрок не найден")
        return

    # Оба должны быть в одном клане в момент передачи
    sender_clan = await clan_service.get_user_clan(session, user.id)
    target_clan = await clan_service.get_user_clan(session, target.id)
    if not sender_clan or not target_clan or sender_clan.id != target_clan.id:
        await message.answer("❌ Игрок больше не в вашем клане")
        return

    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число")
        return

    result = await clan_service.exchange_resource(session, user, target, resource, amount, meta=meta)
    if result["ok"]:
        actual = result.get("amount", amount)
        if actual != amount:
            await message.answer(
                f"✅ Передано {fmt_num(actual)} → <b>{html.escape(target.full_name)}</b> "
                f"(запрошено {fmt_num(amount)}, хранилище получателя заполнено)",
                parse_mode="HTML",
            )
        else:
            await message.answer(
                f"✅ Передано <b>{fmt_num(actual)}</b> → <b>{html.escape(target.full_name)}</b>",
                parse_mode="HTML",
            )
    else:
        await message.answer(f"❌ {result['reason']}")
