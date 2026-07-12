"""Тикеты и прокрутки (pull_one / pull_10)."""
import asyncio
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from collections import Counter

from app.models.user import User
from app.services.cards.gacha import gacha_service
from app.services.cooldown_service import cooldown_service
from app.services.quest_service import quest_service
from app.utils.formatters import fmt_num
from app.data.characters import RANK_CONFIG_MAP, RANK_EMOJI
from app.database import AsyncSessionFactory
from app.bot_instance import get_bot

router = Router()
logger = logging.getLogger(__name__)

RANK_ORDER = [
    "perfection", "absolute", "peak", "legend", "new_legend",
    "gen_zero", "strong_king", "king", "boss", "member",
]


@router.callback_query(F.data == "try_ticket")
async def cb_try_ticket(cb: CallbackQuery, session: AsyncSession, user: User):
    result = await gacha_service.try_get_ticket(session, user)
    if not result["ok"]:
        await cb.answer(f"⏳ {result['reason']}", show_alert=True)
        return

    if result["got"]:
        text = (
            f"🎟🎟 Двойной тикет! +2!\n({result['roll']} ≤ {result['chance']}%)"
            if result.get("double")
            else f"🎟 Тикет получен!\n({result['roll']} ≤ {result['chance']}%)"
        )
    else:
        text = f"😔 Не повезло ({result['roll']} > {result['chance']}%)"

    await cb.answer(text, show_alert=True)
    from app.handlers.cards.menu import cb_deck
    await cb_deck(cb, session, user)


# ── Фоновые задачи ────────────────────────────────────────────────────────────

async def _pull_one_bg(chat_id: int, msg_id: int, user_db_id: int, lock_key: str) -> None:
    bot = get_bot()
    try:
        async with AsyncSessionFactory() as s:
            u = await s.scalar(select(User).where(User.id == user_db_id).with_for_update())
            result = await gacha_service.pull(s, u)
            if result["ok"]:
                await quest_service.add_progress(s, u, "gacha_pull")
            await s.commit()

        if not result["ok"]:
            try:
                await bot.edit_message_text(result["reason"], chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass
            return

        char = result["character"]
        emoji = RANK_EMOJI.get(char["rank"], "❓")

        builder = InlineKeyboardBuilder()
        if u.tickets > 0:
            builder.row(InlineKeyboardButton(
                text=f"🎰 Ещё раз ({u.tickets} тик.)", callback_data="pull_one"
            ))
        builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="deck"))

        caption = (
            f"🎰 <b>Результат!</b>\n\n"
            f"{emoji} <b>{char['name']}</b>\n"
            f"Ранг: {result['rank_label']}\n"
            f"Мощь: {fmt_num(result['power'])}\n\n"
            f"<i>{char.get('desc', '')}</i>\n\n"
            f"🎟 Осталось: {u.tickets}/{ u.max_tickets * 2 if getattr(u, 'circ_ticket_overflow', False) else u.max_tickets}"
        )

        # ── Попытка отправить фото ────────────────────────────────────────────
        from app.utils.card_sender import send_card_photo
        sent_photo = await send_card_photo(
            bot, chat_id, char["name"], caption, builder.as_markup()
        )
        if sent_photo:
            # Удаляем спиннер
            try:
                await bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
        else:
            # Нет изображения — просто редактируем текст
            try:
                await bot.edit_message_text(
                    caption, chat_id=chat_id, message_id=msg_id,
                    reply_markup=builder.as_markup(), parse_mode="HTML",
                )
            except Exception:
                pass

    except Exception:
        logger.error(f"pull error for user_db_id={user_db_id}", exc_info=True)
        try:
            await bot.edit_message_text(
                "⚠️ Ошибка при прокрутке, попробуй снова.",
                chat_id=chat_id, message_id=msg_id,
            )
        except Exception:
            pass
    finally:
        await cooldown_service.clear_cooldown(lock_key)


async def _pull_10_bg(chat_id: int, msg_id: int, user_db_id: int, lock_key: str) -> None:
    bot = get_bot()
    try:
        async with AsyncSessionFactory() as s:
            u = await s.scalar(select(User).where(User.id == user_db_id).with_for_update())
            count = min(10, u.tickets)
            results = await gacha_service.pull_n(s, u, count)
            if results:
                await quest_service.add_progress(s, u, "gacha_pull", amount=count)
            await s.commit()

        if not results:
            try:
                await bot.edit_message_text("Нет тикетов", chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass
            return

        rank_counter: Counter = Counter(r["character"]["rank"] for r in results)
        lines = [f"🎰 <b>Прокрутка {count} тикетов!</b>\n"]
        for rank in RANK_ORDER:
            if rank in rank_counter:
                cfg = RANK_CONFIG_MAP.get(rank)
                label = cfg.label if cfg else rank
                lines.append(f"{RANK_EMOJI.get(rank, '❓')} {label}: ×{rank_counter[rank]}")

        best = max(results, key=lambda x: x["power"])
        best_char = best["character"]
        lines.append(
            f"\n⭐ <b>Лучший:</b> {RANK_EMOJI.get(best_char['rank'], '❓')} "
            f"{best_char['name']} [{best['rank_label']}] — {fmt_num(best['power'])}"
        )

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="deck"))

        caption = "\n".join(lines)

        # ── Попытка отправить фото лучшей карты ──────────────────────────────
        from app.utils.card_sender import send_card_photo
        sent_photo = await send_card_photo(
            bot, chat_id, best_char["name"], caption, builder.as_markup()
        )
        if sent_photo:
            try:
                await bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
        else:
            try:
                await bot.edit_message_text(
                    caption, chat_id=chat_id, message_id=msg_id,
                    reply_markup=builder.as_markup(), parse_mode="HTML",
                )
            except Exception:
                pass

    except Exception:
        logger.error(f"pull error for user_db_id={user_db_id}", exc_info=True)
        try:
            await bot.edit_message_text(
                "⚠️ Ошибка при прокрутке, попробуй снова.",
                chat_id=chat_id, message_id=msg_id,
            )
        except Exception:
            pass
    finally:
        await cooldown_service.clear_cooldown(lock_key)


@router.callback_query(F.data == "pull_one")
async def cb_pull_one(cb: CallbackQuery, session: AsyncSession, user: User):
    lock_key = cooldown_service.pull_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("Подожди...", show_alert=False)
        return
    await cb.answer()
    try:
        await cb.message.edit_text("🎰 Прокручиваем...")
    except Exception:
        pass
    asyncio.create_task(
        _pull_one_bg(cb.message.chat.id, cb.message.message_id, user.id, lock_key)
    )


@router.callback_query(F.data == "pull_10")
async def cb_pull_10(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.tickets <= 0:
        await cb.answer("Нет тикетов", show_alert=True)
        return
    lock_key = cooldown_service.pull_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("Подожди...", show_alert=False)
        return
    await cb.answer()
    try:
        await cb.message.edit_text("🎰 Прокручиваем тикеты...")
    except Exception:
        pass
    asyncio.create_task(
        _pull_10_bg(cb.message.chat.id, cb.message.message_id, user.id, lock_key)
    )
