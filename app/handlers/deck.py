from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.deck_service import deck_service
from app.services.cooldown_service import cooldown_service
from app.repositories.character_repo import character_repo
from app.utils.keyboards.deck import deck_kb
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_power, fmt_num
from app.data.characters import RANK_CONFIG_MAP, RANK_EMOJI

router = Router()


@router.callback_query(F.data == "deck")
async def cb_deck(cb: CallbackQuery, session: AsyncSession, user: User):
    cd = await cooldown_service.get_ttl(cooldown_service.ticket_key(user.id))
    total_char_power = await character_repo.get_total_power(session, user.id)

    from app.utils.formatters import fmt_ttl
    cd_str = f"⏳ {fmt_ttl(cd)}" if cd > 0 else "✅ Готов"

    text = (
        f"🃏 <b>Колода</b>\n\n"
        f"🎟 Тикеты: {user.tickets}/{user.max_tickets}\n"
        f"🍀 Шанс тикета: {user.ticket_chance}%\n"
        f"⏱ КД тикета: {cd_str}\n"
        f"💪 Мощь персонажей: {fmt_num(total_char_power)}"
    )
    await cb.message.edit_text(
        text,
        reply_markup=deck_kb(user.tickets, user.max_tickets, cd),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "try_ticket")
async def cb_try_ticket(cb: CallbackQuery, session: AsyncSession, user: User):
    result = await deck_service.try_get_ticket(session, user)
    if not result["ok"]:
        await cb.answer(f"⏳ {result['reason']}", show_alert=True)
        return

    if result["got"]:
        await cb.answer(f"🎟 Тикет получен! ({result['roll']} ≤ {result['chance']}%)")
    else:
        await cb.answer(f"😔 Не повезло ({result['roll']} > {result['chance']}%)")

    await cb_deck(cb, session, user)


@router.callback_query(F.data == "pull_one")
async def cb_pull_one(cb: CallbackQuery, session: AsyncSession, user: User):
    result = await deck_service.pull(session, user)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    char = result["character"]
    emoji = RANK_EMOJI.get(char["rank"], "❓")
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="deck"))

    await cb.message.edit_text(
        f"🎰 <b>Результат!</b>\n\n"
        f"{emoji} <b>{char['name']}</b>\n"
        f"Ранг: {result['rank_label']}\n"
        f"Мощь: {fmt_num(result['power'])}\n\n"
        f"<i>{char['desc']}</i>\n\n"
        f"🎟 Осталось: {user.tickets}/{user.max_tickets}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "pull_all")
async def cb_pull_all(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.tickets <= 0:
        await cb.answer("Нет тикетов", show_alert=True)
        return

    results = await deck_service.pull_all(session, user)
    if not results:
        await cb.answer("Нет тикетов", show_alert=True)
        return

    lines = [f"🎰 <b>Прокрутка {len(results)} тикетов!</b>\n"]
    for r in results:
        char = r["character"]
        emoji = RANK_EMOJI.get(char["rank"], "❓")
        lines.append(f"{emoji} {char['name']} — {fmt_num(r['power'])}")

    best = max(results, key=lambda x: x["power"])
    lines.append(
        f"\n⭐ Лучший: {best['character']['name']} "
        f"[{best['rank_label']}] — {fmt_num(best['power'])}"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="deck"))
    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "collection")
async def cb_collection(cb: CallbackQuery, session: AsyncSession, user: User):
    from sqlalchemy import select
    from app.models.character import UserCharacter
    from collections import Counter

    result = await session.execute(
        select(UserCharacter).where(UserCharacter.user_id == user.id)
    )
    chars = result.scalars().all()

    if not chars:
        await cb.message.edit_text(
            "📚 <b>Коллекция персонажей</b>\n\nКоллекция пуста",
            reply_markup=back_kb("deck"),
            parse_mode="HTML",
        )
        return

    rank_order = [
        "absolute", "peak", "legend", "new_legend",
        "gen_zero", "strong_king", "king", "boss", "member"
    ]

    # Группируем по рангу
    by_rank = {}
    for c in chars:
        by_rank.setdefault(c.rank, []).append(c)

    total_power = sum(c.power for c in chars)

    # Показываем кнопки по рангам
    builder = InlineKeyboardBuilder()
    for rank in rank_order:
        if rank not in by_rank:
            continue
        cfg = RANK_CONFIG_MAP.get(rank)
        emoji = RANK_EMOJI.get(rank, "❓")
        label = cfg.label if cfg else rank
        cnt = len(by_rank[rank])
        builder.button(
            text=f"{emoji} {label} [{cnt}]",
            callback_data=f"collection_rank:{rank}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="deck"))

    await cb.message.edit_text(
        f"📚 <b>Коллекция персонажей</b>\n\n"
        f"💪 Суммарная мощь: {fmt_num(total_power)}\n\n"
        f"Выбери ранг:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("collection_rank:"))
async def cb_collection_rank(cb: CallbackQuery, session: AsyncSession, user: User):
    rank = cb.data.split(":")[1]
    from sqlalchemy import select
    from app.models.character import UserCharacter
    from collections import Counter

    result = await session.execute(
        select(UserCharacter).where(
            UserCharacter.user_id == user.id,
            UserCharacter.rank == rank,
        )
    )
    chars = result.scalars().all()

    cfg = RANK_CONFIG_MAP.get(rank)
    emoji = RANK_EMOJI.get(rank, "❓")
    label = cfg.label if cfg else rank

    # Группируем по имени
    by_name = Counter(c.character_id for c in chars)
    total_power = sum(c.power for c in chars)

    lines = [f"{emoji} <b>{label} — {len(chars)} персонажей</b>\n"]
    for name, cnt in by_name.items():
        char_data = next((c for c in chars if c.character_id == name), None)
        power = char_data.power if char_data else 0
        cnt_str = f" ×{cnt}" if cnt > 1 else ""
        lines.append(f"• {name}{cnt_str} — {fmt_num(power)} мощи")

    lines.append(f"\n💪 Мощь этого ранга: {fmt_num(total_power)}")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="collection"))
    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )