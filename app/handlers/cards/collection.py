"""Просмотр коллекции карточек и действия: распыление."""
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
from app.services.cards.fusion import fusion_service
from app.utils.formatters import fmt_num, fmt_power
from app.data.characters import RANK_CONFIG_MAP, RANK_EMOJI, CHARACTERS
from app.data.card_images import get_image_path
from app.constants.cards import LEVEL_LABELS, LEVEL_EMOJIS, DUST_PER_LEVEL, FUSION_COST, calc_dust

router = Router()

RANK_ORDER = [
    "perfection", "absolute", "peak", "legend", "new_legend",
    "gen_zero", "strong_king", "king", "boss", "member",
]


async def _safe_edit(cb: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    """Редактирует сообщение. Если не получается (фото и т.п.) — удаляет и присылает новое."""
    try:
        await cb.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


@router.callback_query(F.data == "collection")
async def cb_collection(cb: CallbackQuery, session: AsyncSession, user: User):
    chars = (await session.execute(
        select(UserCharacter).where(UserCharacter.user_id == user.id)
    )).scalars().all()

    if not chars:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🎰 Прокрутить тикет", callback_data="pull_one"))
        builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="deck"))
        await _safe_edit(cb, "📚 <b>Коллекция пуста</b>\n\nПрокрути тикет!",
                         reply_markup=builder.as_markup())
        await cb.answer()
        return

    by_rank: dict[str, list] = defaultdict(list)
    for c in chars:
        by_rank[c.rank].append(c)

    total_power = sum(c.power for c in chars)
    builder = InlineKeyboardBuilder()

    for rank in RANK_ORDER:
        if rank not in by_rank:
            continue
        cfg = RANK_CONFIG_MAP.get(rank)
        emoji = RANK_EMOJI.get(rank, "❓")
        label = cfg.label if cfg else rank
        cnt = len(by_rank[rank])
        rank_power = sum(c.power for c in by_rank[rank])
        builder.button(
            text=f"{emoji} {label} ×{cnt} | {fmt_power(rank_power)}",
            callback_data=f"collection_rank:{rank}",
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="deck"))

    await _safe_edit(
        cb,
        f"📚 <b>Коллекция</b>\n\n"
        f"Всего: {len(chars)} персонажей\n"
        f"💪 Суммарная мощь: {fmt_num(total_power)}\n\n"
        f"Выбери ранг:",
        reply_markup=builder.as_markup(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("collection_rank:"))
async def cb_collection_rank(cb: CallbackQuery, session: AsyncSession, user: User):
    rank = cb.data.split(":")[1]

    chars = (await session.execute(
        select(UserCharacter).where(
            UserCharacter.user_id == user.id,
            UserCharacter.rank == rank,
        ).order_by(UserCharacter.power.desc())
    )).scalars().all()

    cfg = RANK_CONFIG_MAP.get(rank)
    emoji = RANK_EMOJI.get(rank, "❓")
    label = cfg.label if cfg else rank

    by_nl: dict[tuple, list[UserCharacter]] = defaultdict(list)
    for c in chars:
        by_nl[(c.character_id, c.level)].append(c)

    total_power = sum(c.power for c in chars)
    builder = InlineKeyboardBuilder()
    lines = [f"{emoji} <b>{label} — {len(chars)} карточек</b>\n"]

    for (name, level), group in sorted(
        by_nl.items(), key=lambda x: x[1][0].power, reverse=True
    ):
        cnt = len(group)
        lvl_label = LEVEL_LABELS.get(level, f"Ур.{level}")
        lvl_emoji = LEVEL_EMOJIS.get(level, "")
        cnt_str = f" ×{cnt}" if cnt > 1 else ""
        lines.append(
            f"{lvl_emoji} {name} [{lvl_label}]{cnt_str} — {fmt_power(group[0].power)}"
        )
        builder.button(
            text=f"🔍 {name[:20]} [{lvl_label}]{cnt_str}",
            callback_data=f"card_act:{group[0].id}",
        )

    lines.append(f"\n💪 Мощь ранга: {fmt_num(total_power)}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ К коллекции", callback_data="collection"))

    # Может вызываться из фото-сообщения (кнопка «Назад» с превью)
    await _safe_edit(cb, "\n".join(lines), reply_markup=builder.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("card_act:"))
async def cb_card_act(cb: CallbackQuery, session: AsyncSession, user: User):
    uc_id = int(cb.data.split(":")[1])
    uc = await session.get(UserCharacter, uc_id)

    if not uc or uc.user_id != user.id:
        await cb.answer("Карточка не найдена", show_alert=True)
        return

    lvl_label = LEVEL_LABELS.get(uc.level, f"Ур.{uc.level}")
    lvl_emoji = LEVEL_EMOJIS.get(uc.level, "")
    r_emoji = RANK_EMOJI.get(uc.rank, "❓")
    cfg = RANK_CONFIG_MAP.get(uc.rank)
    rank_label = cfg.label if cfg else uc.rank
    dust = calc_dust(uc.rank, uc.level)

    in_deck = bool(await session.scalar(
        select(UserDeck.id).where(
            UserDeck.user_id == user.id, UserDeck.char_id == uc_id
        )
    ))

    # Проверка слияния
    cost = FUSION_COST.get(uc.level)
    fusion_ready = False
    if cost and uc.level < 3:
        from sqlalchemy import func
        available_cnt = await session.scalar(
            select(func.count(UserCharacter.id)).where(
                UserCharacter.user_id == user.id,
                UserCharacter.character_id == uc.character_id,
                UserCharacter.level == uc.level,
            )
        )
        deck_same = await session.scalar(
            select(func.count(UserDeck.id)).join(
                UserCharacter, UserCharacter.id == UserDeck.char_id
            ).where(
                UserDeck.user_id == user.id,
                UserCharacter.character_id == uc.character_id,
                UserCharacter.level == uc.level,
            )
        )
        free_cnt = (available_cnt or 0) - (deck_same or 0)
        fusion_ready = free_cnt >= cost

    char_static = next((c for c in CHARACTERS if c["name"] == uc.character_id), None)
    desc = char_static.get("desc", "") if char_static else ""

    builder = InlineKeyboardBuilder()
    if not in_deck:
        builder.row(InlineKeyboardButton(
            text=f"💨 Распылить (+{dust} 💎)",
            callback_data=f"card_discard:{uc_id}",
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🃏 В колоде — нельзя распылить", callback_data="noop"
        ))
    if fusion_ready:
        next_lbl = LEVEL_LABELS.get(uc.level + 1, "MAX")
        builder.row(InlineKeyboardButton(
            text=f"🔗 Слить → {next_lbl} ({cost} шт.)",
            callback_data=f"card_fuse_confirm:{uc_id}",
        ))
    builder.row(InlineKeyboardButton(
        text="◀️ К рангу", callback_data=f"collection_rank:{uc.rank}"
    ))

    caption = (
        f"{r_emoji} <b>{uc.character_id}</b>\n"
        f"Ранг: {rank_label}\n"
        f"Уровень: {lvl_emoji} {lvl_label}\n"
        f"Мощь: {fmt_power(uc.power)}\n"
        f"Базовая мощь: {fmt_power(uc.base_power)}\n"
        + (f"🃏 <i>В активной колоде</i>\n" if in_deck else "")
        + f"\n<i>{desc}</i>"
    )

    # Если есть изображение — показываем его сразу
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

    await cb.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data.startswith("card_discard:"))
async def cb_card_discard(cb: CallbackQuery, session: AsyncSession, user: User):
    uc_id = int(cb.data.split(":")[1])
    result = await fusion_service.discard_card(session, user, uc_id)
    await session.commit()

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    lvl_label = LEVEL_LABELS.get(result["level"], f"Ур.{result['level']}")
    await cb.answer(
        f"💨 {result['char_name']} [{lvl_label}] распылена!\n+{result['dust']} 💎 пыли",
        show_alert=True,
    )
    await cb_collection(cb, session, user)
