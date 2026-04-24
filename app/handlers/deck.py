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
from app.utils.formatters import fmt_power, fmt_num, fmt_ttl
from app.data.characters import RANK_CONFIG_MAP, RANK_EMOJI, CHARACTERS

router = Router()


@router.callback_query(F.data == "deck")
async def cb_deck(cb: CallbackQuery, session: AsyncSession, user: User):
    cd = await cooldown_service.get_ttl(cooldown_service.ticket_key(user.id))
    total_char_power = await character_repo.get_total_power(session, user.id)
    cd_str = f"⏳ {fmt_ttl(cd)}" if cd > 0 else "✅ Готов"

    builder = InlineKeyboardBuilder()

    # Тикет
    if cd > 0:
        builder.row(InlineKeyboardButton(
            text=f"⏳ Тикет: {fmt_ttl(cd)}",
            callback_data="try_ticket"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🎟 Получить тикет",
            callback_data="try_ticket"
        ))

    # Прокрутка
    if user.tickets > 0:
        builder.row(
            InlineKeyboardButton(
                text=f"🎰 ×1 прокрутка",
                callback_data="pull_one"
            ),
            InlineKeyboardButton(
                text=f"🎰 ×{user.tickets} все",
                callback_data="pull_all"
            )
        )
    else:
        builder.row(InlineKeyboardButton(
            text="🎰 Нет тикетов",
            callback_data="deck_notix"
        ))

    builder.row(InlineKeyboardButton(
        text="📚 Коллекция",
        callback_data="collection"
    ))
    builder.row(InlineKeyboardButton(
        text="📊 Шансы выпадения",
        callback_data="deck_rates"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Главное меню",
        callback_data="main_menu"
    ))

    await cb.message.edit_text(
        f"🃏 <b>Колода</b>\n\n"
        f"🎟 Тикеты: {user.tickets}/{user.max_tickets}\n"
        f"🍀 Шанс тикета: {user.ticket_chance}%\n"
        f"⏱ КД тикета: {cd_str}\n"
        f"💪 Мощь персонажей: {fmt_num(total_char_power)}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "deck_notix")
async def cb_deck_notix(cb: CallbackQuery):
    await cb.answer("Сначала получи тикет!", show_alert=True)


@router.callback_query(F.data == "deck_rates")
async def cb_deck_rates(cb: CallbackQuery, session: AsyncSession, user: User):
    """Таблица шансов выпадения всех рангов и персонажей."""
    from collections import defaultdict

    # Считаем суммарный вес по рангам
    rank_weights: dict[str, float] = defaultdict(float)
    rank_chars: dict[str, list] = defaultdict(list)

    for char in CHARACTERS:
        rank = char["rank"]
        cfg = RANK_CONFIG_MAP.get(rank)
        w = cfg.weight if cfg else 1
        rank_weights[rank] += w
        rank_chars[rank].append(char)

    total_weight = sum(rank_weights.values())

    rank_order = [
        "absolute", "peak", "legend", "new_legend",
        "gen_zero", "strong_king", "king", "boss", "member"
    ]

    lines = ["📊 <b>Шансы выпадения</b>\n"]
    for rank in rank_order:
        if rank not in rank_weights:
            continue
        cfg = RANK_CONFIG_MAP.get(rank)
        emoji = RANK_EMOJI.get(rank, "❓")
        label = cfg.label if cfg else rank
        pct = rank_weights[rank] / total_weight * 100
        chars_in_rank = rank_chars[rank]
        char_names = ", ".join(c["name"] for c in chars_in_rank[:3])
        if len(chars_in_rank) > 3:
            char_names += f" +{len(chars_in_rank)-3}"
        lines.append(
            f"{emoji} <b>{label}</b> — {pct:.2f}%\n"
            f"  {char_names}\n"
        )

    # Также показываем текущий шанс тикета игрока
    from app.services.potion_service import potion_service
    effective_chance = await potion_service.get_effective_ticket_chance(
        session, user
    )
    effective_chance = min(95, effective_chance + user.prestige_ticket_bonus)

    lines.append(f"{'─'*22}")
    lines.append(f"🍀 Твой шанс тикета: {effective_chance}%")
    if user.prestige_ticket_bonus > 0:
        lines.append(f"  ✨ +{user.prestige_ticket_bonus}% от пробуждений")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📋 Список персонажей", callback_data="deck_chars_list"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ К колоде", callback_data="deck"
    ))

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "deck_chars_list")
async def cb_deck_chars_list(cb: CallbackQuery):
    """Полный список персонажей по рангам."""
    rank_order = [
        "absolute", "peak", "legend", "new_legend",
        "gen_zero", "strong_king", "king", "boss", "member"
    ]

    # Группируем
    from collections import defaultdict
    rank_chars: dict[str, list] = defaultdict(list)
    rank_weights: dict[str, float] = defaultdict(float)

    for char in CHARACTERS:
        rank = char["rank"]
        cfg = RANK_CONFIG_MAP.get(rank)
        w = cfg.weight if cfg else 1
        rank_weights[rank] += w
        rank_chars[rank].append(char)

    total_weight = sum(rank_weights.values())

    lines = ["📋 <b>Все персонажи</b>\n"]
    for rank in rank_order:
        if rank not in rank_chars:
            continue
        cfg = RANK_CONFIG_MAP.get(rank)
        emoji = RANK_EMOJI.get(rank, "❓")
        label = cfg.label if cfg else rank
        pct = rank_weights[rank] / total_weight * 100
        lines.append(f"\n{emoji} <b>{label}</b> ({pct:.2f}%):")
        for char in rank_chars[rank]:
            lines.append(
                f"  • {char['name']} — {fmt_num(char['power'])} мощи"
            )

    # Разбиваем на части если слишком длинно
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n...(список обрезан)"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ К шансам", callback_data="deck_rates"
    ))

    try:
        await cb.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "try_ticket")
async def cb_try_ticket(cb: CallbackQuery, session: AsyncSession, user: User):
    result = await deck_service.try_get_ticket(session, user)
    if not result["ok"]:
        await cb.answer(f"⏳ {result['reason']}", show_alert=True)
        return

    if result["got"]:
        await cb.answer(
            f"🎟 Тикет получен!\n({result['roll']} ≤ {result['chance']}%)",
            show_alert=True
        )
    else:
        await cb.answer(
            f"😔 Не повезло ({result['roll']} > {result['chance']}%)",
            show_alert=True
        )

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
    if user.tickets > 0:
        builder.row(InlineKeyboardButton(
            text=f"🎰 Ещё раз ({user.tickets} тик.)",
            callback_data="pull_one"
        ))
    builder.row(InlineKeyboardButton(
        text="◀️ К колоде", callback_data="deck"
    ))

    try:
        await cb.message.edit_text(
            f"🎰 <b>Результат!</b>\n\n"
            f"{emoji} <b>{char['name']}</b>\n"
            f"Ранг: {result['rank_label']}\n"
            f"Мощь: {fmt_num(result['power'])}\n\n"
            f"<i>{char.get('desc', '')}</i>\n\n"
            f"🎟 Осталось: {user.tickets}/{user.max_tickets}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "pull_all")
async def cb_pull_all(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.tickets <= 0:
        await cb.answer("Нет тикетов", show_alert=True)
        return

    count = user.tickets
    results = await deck_service.pull_all(session, user)
    if not results:
        await cb.answer("Нет тикетов", show_alert=True)
        return

    lines = [f"🎰 <b>Прокрутка {count} тикетов!</b>\n"]

    # Группируем по рангу для краткости
    from collections import Counter
    rank_counter: Counter = Counter()
    for r in results:
        rank_counter[r["character"]["rank"]] += 1

    rank_order = [
        "absolute", "peak", "legend", "new_legend",
        "gen_zero", "strong_king", "king", "boss", "member"
    ]
    for rank in rank_order:
        if rank not in rank_counter:
            continue
        emoji = RANK_EMOJI.get(rank, "❓")
        cfg = RANK_CONFIG_MAP.get(rank)
        label = cfg.label if cfg else rank
        lines.append(f"{emoji} {label}: ×{rank_counter[rank]}")

    best = max(results, key=lambda x: x["power"])
    best_emoji = RANK_EMOJI.get(best["character"]["rank"], "❓")
    lines.append(
        f"\n⭐ <b>Лучший:</b> {best_emoji} {best['character']['name']} "
        f"[{best['rank_label']}] — {fmt_num(best['power'])}"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ К колоде", callback_data="deck"
    ))

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "collection")
async def cb_collection(cb: CallbackQuery, session: AsyncSession, user: User):
    from sqlalchemy import select
    from app.models.character import UserCharacter

    result = await session.execute(
        select(UserCharacter).where(UserCharacter.user_id == user.id)
    )
    chars = result.scalars().all()

    if not chars:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="🎰 Прокрутить тикет", callback_data="pull_one"
        ))
        builder.row(InlineKeyboardButton(
            text="◀️ К колоде", callback_data="deck"
        ))
        try:
            await cb.message.edit_text(
                "📚 <b>Коллекция персонажей</b>\n\nКоллекция пуста.\nПрокрути тикет!",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    rank_order = [
        "absolute", "peak", "legend", "new_legend",
        "gen_zero", "strong_king", "king", "boss", "member"
    ]
    by_rank: dict[str, list] = {}
    for c in chars:
        by_rank.setdefault(c.rank, []).append(c)

    total_power = sum(c.power for c in chars)

    builder = InlineKeyboardBuilder()
    for rank in rank_order:
        if rank not in by_rank:
            continue
        cfg = RANK_CONFIG_MAP.get(rank)
        emoji = RANK_EMOJI.get(rank, "❓")
        label = cfg.label if cfg else rank
        cnt = len(by_rank[rank])
        rank_power = sum(c.power for c in by_rank[rank])
        builder.button(
            text=f"{emoji} {label} ×{cnt} | {fmt_num(rank_power)}",
            callback_data=f"collection_rank:{rank}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="◀️ К колоде", callback_data="deck"
    ))

    try:
        await cb.message.edit_text(
            f"📚 <b>Коллекция персонажей</b>\n\n"
            f"Всего: {len(chars)} персонажей\n"
            f"💪 Суммарная мощь: {fmt_num(total_power)}\n\n"
            f"Выбери ранг:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("collection_rank:"))
async def cb_collection_rank(
    cb: CallbackQuery, session: AsyncSession, user: User
):
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

    by_name = Counter(c.character_id for c in chars)
    total_power = sum(c.power for c in chars)

    lines = [f"{emoji} <b>{label} — {len(chars)} персонажей</b>\n"]
    for name, cnt in sorted(by_name.items()):
        char_data = next((c for c in chars if c.character_id == name), None)
        power = char_data.power if char_data else 0
        cnt_str = f" ×{cnt}" if cnt > 1 else ""
        lines.append(f"• {name}{cnt_str} — {fmt_num(power)} мощи")

    lines.append(f"\n💪 Мощь ранга: {fmt_num(total_power)}")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ К коллекции", callback_data="collection"
    ))

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass