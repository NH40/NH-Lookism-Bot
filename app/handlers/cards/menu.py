"""Главное меню колоды + шансы выпадения."""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict

from app.models.user import User
from app.services.cooldown_service import cooldown_service
from app.repositories.character_repo import character_repo
from app.utils.formatters import fmt_num, fmt_ttl
from app.data.characters import RANK_CONFIG_MAP, RANK_EMOJI, CHARACTERS
from app.services.potion_service import potion_service
from app.constants.cards import TICKET_CRAFT_COST

router = Router()

RANK_ORDER = [
    "perfection", "absolute", "peak", "legend", "new_legend",
    "gen_zero", "strong_king", "king", "boss", "member",
]


@router.callback_query(F.data == "deck")
async def cb_deck(cb: CallbackQuery, session: AsyncSession, user: User):
    cd = await cooldown_service.get_ttl(cooldown_service.ticket_key(user.id))
    total_char_power = await character_repo.get_total_power(session, user.id)
    cd_str = f"⏳ {fmt_ttl(cd)}" if cd > 0 else "✅ Готов"

    cap = getattr(user, "max_ticket_chance", 70)
    effective_chance = await potion_service.get_effective_ticket_chance(session, user)
    effective_chance = min(
        cap,
        effective_chance + user.prestige_ticket_bonus
        + getattr(user, "clan_ticket_bonus", 0)
        + getattr(user, "clan_donat_ticket_bonus", 0),
    )
    dust = getattr(user, "card_dust", 0)

    builder = InlineKeyboardBuilder()
    if cd > 0:
        builder.row(InlineKeyboardButton(text=f"⏳ Тикет: {fmt_ttl(cd)}", callback_data="try_ticket"))
    else:
        builder.row(InlineKeyboardButton(text="🎟 Получить тикет", callback_data="try_ticket"))

    if user.tickets > 0:
        builder.row(
            InlineKeyboardButton(text="🎰 ×1 прокрутка", callback_data="pull_one"),
            InlineKeyboardButton(text="🎰 ×10", callback_data="pull_10"),
        )
    else:
        builder.row(InlineKeyboardButton(text="🎰 Нет тикетов", callback_data="deck_notix"))

    builder.row(
        InlineKeyboardButton(text="📚 Коллекция", callback_data="collection"),
        InlineKeyboardButton(text="🃏 Моя колода", callback_data="my_deck"),
    )
    builder.row(
        InlineKeyboardButton(text="🔗 Слияние", callback_data="fusion_menu"),
        InlineKeyboardButton(text="⚔️ Дуэли", callback_data="duel_menu"),
    )
    builder.row(InlineKeyboardButton(text="📊 Шансы", callback_data="deck_rates"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    text = (
        f"🃏 <b>Колода</b>\n\n"
        f"🎟 Тикеты: {user.tickets}/{user.max_tickets}\n"
        f"🍀 Шанс тикета: {effective_chance}%\n"
        f"⏱ КД тикета: {cd_str}\n"
        f"💎 Пыль: {fmt_num(dust)}\n"
        f"💪 Мощь персонажей: {fmt_num(total_char_power)}"
    )
    markup = builder.as_markup()
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        # Сообщение — фото (результат гачи с картинкой) — удаляем и присылаем текст
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "deck_notix")
async def cb_deck_notix(cb: CallbackQuery):
    await cb.answer("Сначала получи тикет!", show_alert=True)


def _build_rank_weights() -> tuple[dict[str, float], dict[str, list], float]:
    """Возвращает фиксированные шансы рангов (weight = % ранга) и список персонажей."""
    rank_weights: dict[str, float] = {}
    rank_chars: dict[str, list] = defaultdict(list)
    for char in CHARACTERS:
        rank_chars[char["rank"]].append(char)
    for rank, cfg in RANK_CONFIG_MAP.items():
        rank_weights[rank] = cfg.weight
    total = sum(rank_weights.values())  # = 100.0
    return rank_weights, rank_chars, total


@router.callback_query(F.data == "deck_rates")
async def cb_deck_rates(cb: CallbackQuery, session: AsyncSession, user: User):
    rank_weights, rank_chars, total_weight = _build_rank_weights()

    cap = getattr(user, "max_ticket_chance", 70)
    ec = await potion_service.get_effective_ticket_chance(session, user)
    ec = min(cap, ec + user.prestige_ticket_bonus
             + getattr(user, "clan_ticket_bonus", 0)
             + getattr(user, "clan_donat_ticket_bonus", 0))

    lines = ["📊 <b>Шансы выпадения</b>\n"]
    builder = InlineKeyboardBuilder()

    for rank in RANK_ORDER:
        if rank not in rank_weights:
            continue
        cfg = RANK_CONFIG_MAP.get(rank)
        emoji = RANK_EMOJI.get(rank, "❓")
        label = cfg.label if cfg else rank
        pct = rank_weights[rank] / total_weight * 100
        count = len(rank_chars[rank])
        lines.append(f"{emoji} <b>{label}</b> — {pct:.2f}%  ({count} персонажей)")
        builder.row(InlineKeyboardButton(
            text=f"{emoji} {label} — {pct:.2f}%",
            callback_data=f"deck_rates_rank:{rank}"
        ))

    lines.append(f"\n{'─'*22}\n🍀 Твой шанс тикета: {ec}%")
    lines.append("Нажми на ранг — увидишь всех персонажей")

    builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="deck"))

    text = "\n".join(lines)
    markup = builder.as_markup()
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data.startswith("deck_rates_rank:"))
async def cb_deck_rates_rank(cb: CallbackQuery):
    rank = cb.data.split(":")[1]
    rank_weights, rank_chars, total_weight = _build_rank_weights()

    chars = rank_chars.get(rank, [])
    cfg = RANK_CONFIG_MAP.get(rank)
    emoji = RANK_EMOJI.get(rank, "❓")
    label = cfg.label if cfg else rank
    pct = rank_weights.get(rank, 0) / total_weight * 100 if total_weight else 0

    lines = [f"{emoji} <b>{label}</b> — {pct:.2f}%\n"]
    lines.append(f"Всего персонажей: <b>{len(chars)}</b>\n")

    for i, char in enumerate(chars, 1):
        lines.append(f"{i}. {char['name']}")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К шансам", callback_data="deck_rates"))

    text = "\n".join(lines)
    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await cb.answer()
