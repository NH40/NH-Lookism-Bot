from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.clan import ClanMember
from app.services.clan import clan_service
from app.utils.formatters import fmt_num
import html

router = Router()


class ExchangeFSM(StatesGroup):
    waiting_amount = State()
    waiting_squad_rank = State()
    waiting_char_select = State()


RESOURCES = [
    ("coins",          "💰 NHCoin"),
    ("tickets",        "🎟 Тикеты"),
    ("mastery_points", "⭐ Очки мастерства"),
    ("ui_fragments",   "🔮 Фрагменты УИ"),
    ("path_points",    "🔷 Очки пути"),
    ("squad",          "👥 Статисты"),
    ("character",      "🎴 Персонаж"),
]


@router.callback_query(F.data == "clan_exchange")
async def cb_clan_exchange(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return
    members = await clan_service.get_clan_members(session, clan.id)
    other_members = [m for m in members if m.user_id != user.id]
    if not other_members:
        await cb.answer("В клане нет других участников", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    for m in other_members:
        target = await session.scalar(select(User).where(User.id == m.user_id))
        if target:
            builder.row(InlineKeyboardButton(
                text=f"👤 {html.escape(target.full_name)} | 💪{fmt_num(target.combat_power)}",
                callback_data=f"clan_exch_target:{target.id}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))
    try:
        await cb.message.edit_text(
            "🔄 <b>Обмен ресурсами</b>\n\nВыбери участника:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_exch_target:"))
async def cb_clan_exch_target(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    target_id = int(cb.data.split(":")[1])
    target = await session.scalar(select(User).where(User.id == target_id))
    if not target:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    await state.update_data(target_id=target_id)
    builder = InlineKeyboardBuilder()
    for res_id, res_name in RESOURCES:
        builder.row(InlineKeyboardButton(text=res_name, callback_data=f"clan_exch_res:{target_id}:{res_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_exchange"))
    try:
        await cb.message.edit_text(
            f"🔄 Обмен с <b>{html.escape(target.full_name)}</b>\n\nВыбери ресурс:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_exch_res:"))
async def cb_clan_exch_res(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    parts = cb.data.split(":")
    target_id = int(parts[1])
    resource = parts[2]

    if resource == "squad":
        # Показываем выбор ранга статистов
        from app.data.squad import RANKS_BY_ID, PHASE_RANKS
        from app.models.squad_member import SquadMember
        from sqlalchemy import func

        # Считаем статистов по рангам у игрока
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
                callback_data=f"clan_exch_squad_rank:{target_id}:{rank}"
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
        # Показываем персонажей по рангам
        from app.models.character import UserCharacter
        from app.data.characters import RANK_EMOJI, RANK_CONFIG_MAP
        from collections import Counter
        result = await session.execute(
            select(UserCharacter).where(UserCharacter.user_id == user.id)
        )
        chars = result.scalars().all()
        by_rank: dict = {}
        for c in chars:
            by_rank.setdefault(c.rank, []).append(c)

        builder = InlineKeyboardBuilder()
        rank_order = ["absolute","peak","legend","new_legend","gen_zero","strong_king","king","boss","member"]
        for rank in rank_order:
            if rank not in by_rank:
                continue
            emoji = RANK_EMOJI.get(rank, "•")
            cfg = RANK_CONFIG_MAP.get(rank)
            label = cfg.label if cfg else rank
            builder.row(InlineKeyboardButton(
                text=f"{emoji} {label} × {len(by_rank[rank])}",
                callback_data=f"clan_exch_char_rank:{target_id}:{rank}"
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

    # Обычные ресурсы — вводим количество
    await state.set_state(ExchangeFSM.waiting_amount)
    await state.update_data(target_id=target_id, resource=resource)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"clan_exch_target:{target_id}"))
    try:
        await cb.message.edit_text("🔄 Введите количество для передачи:", reply_markup=cancel_kb.as_markup())
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_exch_squad_rank:"))
async def cb_clan_exch_squad_rank(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    parts = cb.data.split(":")
    target_id = int(parts[1])
    rank = parts[2]

    from app.models.squad_member import SquadMember
    from sqlalchemy import func
    count = await session.scalar(
        select(func.count(SquadMember.id)).where(SquadMember.user_id == user.id, SquadMember.rank == rank)
    )

    await state.set_state(ExchangeFSM.waiting_amount)
    await state.update_data(target_id=target_id, resource="squad", meta={"rank": rank})

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"clan_exch_target:{target_id}"))
    try:
        await cb.message.edit_text(
            f"👥 Передача статистов ранга <b>{rank}</b>\nДоступно: {count}\n\nВведите количество:",
            reply_markup=cancel_kb.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_exch_char_rank:"))
async def cb_clan_exch_char_rank(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    parts = cb.data.split(":")
    target_id = int(parts[1])
    rank = parts[2]

    from app.models.character import UserCharacter
    from app.data.characters import RANK_EMOJI
    result = await session.execute(
        select(UserCharacter).where(UserCharacter.user_id == user.id, UserCharacter.rank == rank)
    )
    chars = result.scalars().all()

    builder = InlineKeyboardBuilder()
    for char in chars:
        builder.row(InlineKeyboardButton(
            text=f"🎴 {char.character_id} | {fmt_num(char.power)} мощи",
            callback_data=f"clan_exch_char_select:{target_id}:{char.id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"clan_exch_res:{target_id}:character"))
    try:
        await cb.message.edit_text(
            f"🎴 Выбери персонажа для передачи:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_exch_char_select:"))
async def cb_clan_exch_char_select(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    parts = cb.data.split(":")
    target_id = int(parts[1])
    char_id = int(parts[2])

    target = await session.scalar(select(User).where(User.id == target_id))
    result = await clan_service.exchange_resource(
        session, user, target, "character", 1, meta={"char_id": char_id}
    )
    if result["ok"]:
        await cb.answer(f"✅ Персонаж передан {html.escape(target.full_name)}!", show_alert=True)
    else:
        await cb.answer(result["reason"], show_alert=True)


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

    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число")
        return

    result = await clan_service.exchange_resource(session, user, target, resource, amount, meta=meta)
    if result["ok"]:
        await message.answer(f"✅ Ресурс передан {html.escape(target.full_name)}!", parse_mode="HTML")
    else:
        await message.answer(f"❌ {result['reason']}")