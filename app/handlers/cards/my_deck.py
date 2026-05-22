"""Управление активной колодой из 5 слотов.

Флоу выбора карточки:
  deck_slot:{slot}
    → (занят) показывает опции: заменить / убрать
    → (пуст)  deck_slot_pick:{slot}   — выбор ранга
        → deck_slot_rank:{slot}:{rank}  — карточки этого ранга
            → deck_slot_preview:{slot}:{uc_id}  — превью с фото
                → deck_slot_set:{slot}:{uc_id}   — ставим в слот
                → deck_slot_rank:{slot}:{rank}   — назад к рангу
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from collections import defaultdict

from app.models.user import User
from app.models.character import UserCharacter
from app.models.card_deck import UserDeck
from app.services.cards.deck_slots import deck_slot_service
from app.utils.formatters import fmt_power
from app.data.characters import RANK_EMOJI, RANK_CONFIG_MAP
from app.data.card_images import get_image_path
from app.constants.cards import LEVEL_LABELS, LEVEL_EMOJIS

router = Router()

RANK_ORDER = [
    "perfection", "absolute", "peak", "legend", "new_legend",
    "gen_zero", "strong_king", "king", "boss", "member",
]


async def _safe_edit(cb: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    """edit_text если получится, иначе — delete + answer."""
    try:
        await cb.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


# ── Главное меню колоды ───────────────────────────────────────────────────────

@router.callback_query(F.data == "my_deck")
async def cb_my_deck(cb: CallbackQuery, session: AsyncSession, user: User):
    deck_slots = await deck_slot_service.get_deck(session, user.id)
    slot_map = {d.slot: d for d in deck_slots}

    # Batch-load all UserCharacter rows for deck slots in one query (avoids N+1)
    char_ids = [d.char_id for d in deck_slots]
    if char_ids:
        uc_rows = (await session.execute(
            select(UserCharacter).where(UserCharacter.id.in_(char_ids))
        )).scalars().all()
        uc_map = {uc.id: uc for uc in uc_rows}
    else:
        uc_map = {}

    lines = ["🃏 <b>Активная колода</b>\n", "5 карточек для дуэлей:\n"]
    builder = InlineKeyboardBuilder()

    total_power = 0
    for slot in range(1, 6):
        if slot in slot_map:
            uc = uc_map.get(slot_map[slot].char_id)
            if uc:
                lvl_lbl = LEVEL_LABELS.get(uc.level, f"Ур.{uc.level}")
                r_emoji = RANK_EMOJI.get(uc.rank, "❓")
                total_power += uc.power
                lines.append(f"[{slot}] {r_emoji} {uc.character_id} [{lvl_lbl}] — {fmt_power(uc.power)}")
                builder.button(
                    text=f"[{slot}] {uc.character_id[:16]} [{lvl_lbl}]",
                    callback_data=f"deck_slot:{slot}",
                )
                continue
        lines.append(f"[{slot}] — пустой слот")
        builder.button(text=f"[{slot}] + Добавить", callback_data=f"deck_slot:{slot}")

    if total_power > 0:
        lines.append(f"\n💪 Мощь колоды: {fmt_power(total_power)}")

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="deck"))

    await _safe_edit(cb, "\n".join(lines), reply_markup=builder.as_markup())
    await cb.answer()


# ── Управление конкретным слотом ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("deck_slot:"))
async def cb_deck_slot(cb: CallbackQuery, session: AsyncSession, user: User):
    slot = int(cb.data.split(":")[1])

    current = await session.scalar(
        select(UserDeck).where(UserDeck.user_id == user.id, UserDeck.slot == slot)
    )

    if current:
        uc = await session.get(UserCharacter, current.char_id)
        name = uc.character_id if uc else "?"
        lvl_lbl = LEVEL_LABELS.get(uc.level if uc else 0, "Ур.0")
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔄 Заменить", callback_data=f"deck_slot_pick:{slot}"),
            InlineKeyboardButton(text="🗑 Убрать", callback_data=f"deck_slot_clear:{slot}"),
        )
        builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="my_deck"))
        await _safe_edit(
            cb,
            f"🃏 Слот {slot}: <b>{name}</b> [{lvl_lbl}]\n\nЧто сделать?",
            reply_markup=builder.as_markup(),
        )
    else:
        await _show_rank_picker(cb, session, user, slot)
    await cb.answer()


@router.callback_query(F.data.startswith("deck_slot_clear:"))
async def cb_deck_slot_clear(cb: CallbackQuery, session: AsyncSession, user: User):
    slot = int(cb.data.split(":")[1])
    await deck_slot_service.clear_deck_slot(session, user, slot)
    await session.commit()
    await cb.answer(f"Слот {slot} очищен")
    await cb_my_deck(cb, session, user)


# ── Шаг 1: выбор ранга ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("deck_slot_pick:"))
async def cb_deck_slot_pick(cb: CallbackQuery, session: AsyncSession, user: User):
    slot = int(cb.data.split(":")[1])
    await _show_rank_picker(cb, session, user, slot)
    await cb.answer()


async def _show_rank_picker(
    cb: CallbackQuery, session: AsyncSession, user: User, slot: int
) -> None:
    """Показывает кнопки рангов (только те, где есть карточки у игрока)."""
    chars = (await session.execute(
        select(UserCharacter).where(UserCharacter.user_id == user.id)
    )).scalars().all()

    if not chars:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="my_deck"))
        await _safe_edit(
            cb,
            "📭 У тебя нет карточек.\nПрокрути тикет в разделе колоды!",
            reply_markup=builder.as_markup(),
        )
        return

    # Группируем по рангу
    by_rank: dict[str, list] = defaultdict(list)
    for c in chars:
        by_rank[c.rank].append(c)

    builder = InlineKeyboardBuilder()
    lines = [f"🃏 <b>Слот {slot} — выбери ранг:</b>\n"]

    for rank in RANK_ORDER:
        if rank not in by_rank:
            continue
        cfg = RANK_CONFIG_MAP.get(rank)
        emoji = RANK_EMOJI.get(rank, "❓")
        label = cfg.label if cfg else rank
        cnt = len(by_rank[rank])
        best_power = max(c.power for c in by_rank[rank])
        lines.append(f"{emoji} {label} ×{cnt} | лучшая {fmt_power(best_power)}")
        builder.button(
            text=f"{emoji} {label} ×{cnt}",
            callback_data=f"deck_slot_rank:{slot}:{rank}",
        )

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="my_deck"))

    await _safe_edit(cb, "\n".join(lines), reply_markup=builder.as_markup())


# ── Шаг 2: список карточек ранга ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("deck_slot_rank:"))
async def cb_deck_slot_rank(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    slot, rank = int(parts[1]), parts[2]

    chars = (await session.execute(
        select(UserCharacter).where(
            UserCharacter.user_id == user.id,
            UserCharacter.rank == rank,
        ).order_by(UserCharacter.power.desc())
    )).scalars().all()

    deck_ids = await deck_slot_service.get_deck_char_ids(session, user.id)

    cfg = RANK_CONFIG_MAP.get(rank)
    emoji = RANK_EMOJI.get(rank, "❓")
    label = cfg.label if cfg else rank

    builder = InlineKeyboardBuilder()
    lines = [f"{emoji} <b>{label} — выбери карточку для слота {slot}:</b>\n"]

    for uc in chars:
        lvl_lbl = LEVEL_LABELS.get(uc.level, f"Ур.{uc.level}")
        lvl_emoji = LEVEL_EMOJIS.get(uc.level, "")
        in_deck_mark = " 🃏" if uc.id in deck_ids else ""
        has_art = "🖼 " if get_image_path(uc.character_id) else ""
        lines.append(
            f"{lvl_emoji} {uc.character_id} [{lvl_lbl}] — {fmt_power(uc.power)}{in_deck_mark}"
        )
        builder.button(
            text=f"{has_art}{uc.character_id[:18]} [{lvl_lbl}]{in_deck_mark}",
            callback_data=f"deck_slot_preview:{slot}:{uc.id}",
        )

    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="◀️ Назад к рангам", callback_data=f"deck_slot_pick:{slot}"
    ))

    await _safe_edit(cb, "\n".join(lines), reply_markup=builder.as_markup())
    await cb.answer()


# ── Шаг 3: превью карточки с фото ────────────────────────────────────────────

@router.callback_query(F.data.startswith("deck_slot_preview:"))
async def cb_deck_slot_preview(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    slot, uc_id = int(parts[1]), int(parts[2])

    uc = await session.get(UserCharacter, uc_id)
    if not uc or uc.user_id != user.id:
        await cb.answer("Карточка не найдена", show_alert=True)
        return

    deck_ids = await deck_slot_service.get_deck_char_ids(session, user.id)
    already_in = uc.id in deck_ids

    lvl_label = LEVEL_LABELS.get(uc.level, f"Ур.{uc.level}")
    lvl_emoji = LEVEL_EMOJIS.get(uc.level, "")
    r_emoji = RANK_EMOJI.get(uc.rank, "❓")
    cfg = RANK_CONFIG_MAP.get(uc.rank)
    rank_label = cfg.label if cfg else uc.rank

    builder = InlineKeyboardBuilder()
    if already_in:
        builder.row(InlineKeyboardButton(
            text=f"✅ Уже в колоде → поставить в слот {slot}",
            callback_data=f"deck_slot_set:{slot}:{uc_id}",
        ))
    else:
        builder.row(InlineKeyboardButton(
            text=f"✅ Поставить в слот {slot}",
            callback_data=f"deck_slot_set:{slot}:{uc_id}",
        ))
    builder.row(InlineKeyboardButton(
        text=f"◀️ Назад к {rank_label}",
        callback_data=f"deck_slot_rank:{slot}:{uc.rank}",
    ))

    caption = (
        f"{r_emoji} <b>{uc.character_id}</b>\n"
        f"Ранг: {rank_label}\n"
        f"Уровень: {lvl_emoji} {lvl_label}\n"
        f"Мощь: {fmt_power(uc.power)}"
        + ("\n🃏 <i>Уже в колоде</i>" if already_in else "")
    )

    await cb.answer()

    # Если есть изображение — показываем фото
    if get_image_path(uc.character_id):
        from app.bot_instance import get_bot
        from app.utils.card_sender import send_card_photo
        bot = get_bot()
        try:
            await cb.message.delete()
        except Exception:
            pass
        sent = await send_card_photo(
            bot, cb.message.chat.id, uc.character_id, caption, builder.as_markup()
        )
        if not sent:
            await cb.message.answer(caption, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await _safe_edit(cb, caption, reply_markup=builder.as_markup())


# ── Шаг 4: подтверждение выбора ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("deck_slot_set:"))
async def cb_deck_slot_set(cb: CallbackQuery, session: AsyncSession, user: User):
    _, slot_s, uc_id_s = cb.data.split(":")
    slot, uc_id = int(slot_s), int(uc_id_s)

    result = await deck_slot_service.set_deck_slot(session, user, slot, uc_id)
    await session.commit()

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    await cb.answer(f"✅ Карточка поставлена в слот {slot}")
    await cb_my_deck(cb, session, user)
