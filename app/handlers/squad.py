from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.squad_service import squad_service, PHASE_RANK_WEIGHTS, _calc_recruit_count
from app.services.cooldown_service import cooldown_service
from app.repositories.squad_repo import squad_repo
from app.utils.keyboards.squad import squad_kb
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num, fmt_power
from app.data.squad import RANKS_BY_ID

router = Router()


RANK_EMOJI = {
    "E": "⚪", "D": "🟢", "C": "🔵",
    "B": "🟣", "A": "🟡", "S": "🔴",
}


def _phase_ranks_str(phase: str) -> str:
    weights = PHASE_RANK_WEIGHTS.get(phase, {})
    parts = []
    for rank in weights:
        emoji = RANK_EMOJI.get(rank, "")
        parts.append(f"{emoji}{rank}")
    return " ".join(parts)


@router.callback_query(F.data == "squad")
async def cb_squad(cb: CallbackQuery, session: AsyncSession, user: User):
    recruit_cd = await cooldown_service.get_ttl(cooldown_service.recruit_key(user.id))
    train_cd = await cooldown_service.get_ttl(cooldown_service.train_key(user.id))
    squad_count = await squad_repo.get_squad_count(session, user.id)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    from app.utils.formatters import fmt_ttl

    builder = InlineKeyboardBuilder()
    train_text = f"⏳ {fmt_ttl(train_cd)}" if train_cd > 0 else "💪 Усилить отряд"
    rec_text = f"⏳ {fmt_ttl(recruit_cd)}" if recruit_cd > 0 else "📢 Вербовка в отряд"
    builder.row(InlineKeyboardButton(text=train_text, callback_data="do_train"))
    builder.row(InlineKeyboardButton(text=rec_text,   callback_data="do_recruit"))
    builder.row(InlineKeyboardButton(text="🗒 Состав армии", callback_data="squad_list"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))

    ranks_str = _phase_ranks_str(user.phase)

    text = (
        f"👥 <b>Группировка</b>\n\n"
        f"👤 Бойцов в отряде: {squad_count}\n"
        f"💪 Боевая мощь: {fmt_num(user.combat_power)}\n"
        f"⚡ Влияние: {fmt_num(user.influence)}\n\n"
        f"🏅 Доступные ранги: {ranks_str}\n"
        f"<i>Влияние открывает более высокие ранги</i>\n\n"
        f"Выбери действие:"
    )
    await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "do_recruit")
async def cb_do_recruit(cb: CallbackQuery, session: AsyncSession, user: User):
    result = await squad_service.recruit(session, user)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    rank_order = ["S", "A", "B", "C", "D", "E"]
    rank_lines = []
    for rank in rank_order:
        cnt = result["rank_counts"].get(rank, 0)
        if cnt:
            emoji = RANK_EMOJI.get(rank, "")
            rank_cfg = RANKS_BY_ID.get(rank)
            rank_lines.append(
                f"  {emoji} Ранг {rank} — {cnt} бойцов "
                f"({rank_cfg.base_power:,} силы каждый)"
            )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К группировке", callback_data="squad"))

    await cb.message.edit_text(
        f"📢 <b>Вербовка завершена!</b>\n\n"
        f"Завербовано: {result['count']} бойцов\n\n"
        + "\n".join(rank_lines) +
        f"\n\n💪 Боевая мощь: {fmt_num(user.combat_power)}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "do_train")
async def cb_do_train(cb: CallbackQuery, session: AsyncSession, user: User):
    result = await squad_service.train(session, user)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    second_str = " (2-я тренировка)" if result.get("is_second") else ""

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К группировке", callback_data="squad"))

    await cb.message.edit_text(
        f"💪 <b>Тренировка{second_str} завершена!</b>\n\n"
        f"Участвовало: {result['trained']} бойцов\n"
        f"Охват: {result['coverage_pct']}% | Шанс: {result['success_chance']}%\n\n"
        f"✅ Прошли тренировку: {result['upgraded']}\n"
        f"❌ Не смогли: {result['failed']}\n"
        f"⭐ Звёзд добавлено: +{result['stars_added']}\n\n"
        f"💪 Боевая мощь: {fmt_num(user.combat_power)}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "squad_list")
async def cb_squad_list(cb: CallbackQuery, session: AsyncSession, user: User):
    from sqlalchemy import select
    from app.models.squad_member import SquadMember
    from collections import Counter

    result = await session.execute(
        select(SquadMember).where(SquadMember.user_id == user.id)
    )
    members = result.scalars().all()

    if not members:
        await cb.message.edit_text(
            "🗒 <b>Состав армии</b>\n\nОтряд пуст",
            reply_markup=back_kb("squad"),
            parse_mode="HTML",
        )
        return

    rank_order = ["S", "A", "B", "C", "D", "E"]
    lines = ["🗒 <b>Состав армии</b>\n"]

    for rank in rank_order:
        rank_members = [m for m in members if m.rank == rank]
        if not rank_members:
            continue

        rank_cfg = RANKS_BY_ID.get(rank)
        emoji = RANK_EMOJI.get(rank, "")
        lines.append(f"\n{emoji} Ранг {rank} — {len(rank_members)} бойцов")

        # Группируем по звёздам
        star_counts = Counter(m.stars for m in rank_members)
        for stars in range(5, -1, -1):
            cnt = star_counts.get(stars, 0)
            if cnt:
                filled = "★" * stars
                empty = "☆" * (5 - stars)
                lines.append(f"  {filled}{empty} × {cnt}")

    total = len(members)
    five_star = sum(1 for m in members if m.stars == 5)
    lines.append(f"\n{'─' * 20}")
    lines.append(f"👥 Всего бойцов: {total}")
    lines.append(f"💪 Боевая мощь: {fmt_num(user.combat_power)}")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К группировке", callback_data="squad"))

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )