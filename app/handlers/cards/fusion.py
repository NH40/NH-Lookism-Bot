"""Меню слияния карточек и подтверждение/выполнение слияния."""
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
from app.services.quest_service import quest_service
from app.utils.formatters import fmt_power
from app.data.characters import RANK_EMOJI
from app.constants.cards import LEVEL_LABELS, LEVEL_EMOJIS, FUSION_COST

router = Router()


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


@router.callback_query(F.data == "fusion_menu")
async def cb_fusion_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    """Показывает персонажей с достаточным числом дубликатов для слияния."""
    chars = (await session.execute(
        select(UserCharacter).where(UserCharacter.user_id == user.id)
    )).scalars().all()

    if not chars:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="deck"))
        await _safe_edit(
            cb, "🔗 <b>Слияние</b>\n\nКоллекция пуста.",
            reply_markup=builder.as_markup(),
        )
        await cb.answer()
        return

    # Не считаем карточки из активной колоды
    deck_ids = set((await session.execute(
        select(UserDeck.char_id).where(UserDeck.user_id == user.id)
    )).scalars().all())

    counter: dict[tuple, int] = defaultdict(int)
    sample_uc: dict[tuple, UserCharacter] = {}
    for c in chars:
        if c.id not in deck_ids:
            key = (c.character_id, c.level)
            counter[key] += 1
            if key not in sample_uc:
                sample_uc[key] = c

    fuseable = [
        (name, level, cnt, sample_uc[(name, level)])
        for (name, level), cnt in counter.items()
        if (cost := FUSION_COST.get(level)) and level < 3 and cnt >= cost
    ]

    builder = InlineKeyboardBuilder()

    if fuseable:
        lines = [f"🔗 <b>Слияние</b>\n\nГотово к слиянию ({len(fuseable)}):\n"]
        for name, level, cnt, sample in fuseable[:10]:
            lvl_lbl = LEVEL_LABELS.get(level, f"Ур.{level}")
            next_lbl = LEVEL_LABELS.get(level + 1, "MAX")
            r_emoji = RANK_EMOJI.get(sample.rank, "❓")
            cost = FUSION_COST[level]
            lines.append(f"{r_emoji} {name} [{lvl_lbl}] ×{cnt} → {next_lbl}")
            builder.button(
                text=f"🔗 {name[:18]} [{lvl_lbl}]→{next_lbl}",
                callback_data=f"card_fuse_confirm:{sample.id}",
            )
    else:
        lines = ["🔗 <b>Слияние</b>\n\nНет готовых слияний.\n\n📈 Прогресс:"]
        progress_items = [
            (name, level, cnt)
            for (name, level), cnt in counter.items()
            if FUSION_COST.get(level) and level < 3
        ]
        progress_items.sort(key=lambda x: x[2], reverse=True)
        for name, level, cnt in progress_items[:8]:
            cost = FUSION_COST[level]
            lvl_lbl = LEVEL_LABELS.get(level, f"Ур.{level}")
            lines.append(f"• {name} [{lvl_lbl}]: {cnt}/{cost}")

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="deck"))

    await _safe_edit(cb, "\n".join(lines), reply_markup=builder.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("card_fuse_confirm:"))
async def cb_card_fuse_confirm(cb: CallbackQuery, session: AsyncSession, user: User):
    uc_id = int(cb.data.split(":")[1])
    uc = await session.get(UserCharacter, uc_id)
    if not uc or uc.user_id != user.id:
        await cb.answer("Карточка не найдена", show_alert=True)
        return

    cost = FUSION_COST.get(uc.level, 5)
    next_lbl = LEVEL_LABELS.get(uc.level + 1, "MAX")
    lvl_lbl = LEVEL_LABELS.get(uc.level, f"Ур.{uc.level}")

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"card_fuse_do:{uc_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="fusion_menu"),
    )

    await _safe_edit(
        cb,
        f"🔗 <b>Слияние</b>\n\n"
        f"Персонаж: <b>{uc.character_id}</b>\n"
        f"Текущий уровень: {lvl_lbl}\n"
        f"Нужно карточек: {cost}×\n"
        f"Результат: <b>{next_lbl}</b>\n\n"
        f"⚠️ <b>{cost} карточек вне колоды будут уничтожены.</b>",
        reply_markup=builder.as_markup(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("card_fuse_do:"))
async def cb_card_fuse_do(cb: CallbackQuery, session: AsyncSession, user: User):
    uc_id = int(cb.data.split(":")[1])
    uc = await session.get(UserCharacter, uc_id)
    if not uc or uc.user_id != user.id:
        await cb.answer("Карточка не найдена", show_alert=True)
        return

    result = await fusion_service.fuse_cards(session, user, uc.character_id, uc.level)
    if result["ok"]:
        await quest_service.add_progress(session, user, "card_fusion")
    await session.commit()

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    new_lbl = LEVEL_LABELS.get(result["new_level"], f"Ур.{result['new_level']}")
    await cb.answer(
        f"🔗 Слияние успешно!\n"
        f"{result['char_name']} → {new_lbl}\n"
        f"Мощь: {fmt_power(result['new_power'])}",
        show_alert=True,
    )
    await cb_fusion_menu(cb, session, user)
