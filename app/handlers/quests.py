from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from app.models.user import User
from app.services.quest_service import quest_service
from app.constants.quests import QUESTS_BY_ID
from app.utils.formatters import fmt_num

router = Router()


@router.callback_query(F.data == "daily_quests")
async def cb_daily_quests(cb: CallbackQuery, session: AsyncSession, user: User):
    quests = await quest_service.get_or_create_quests(session, user)

    builder = InlineKeyboardBuilder()
    lines = ["📋 <b>Ежедневные задания</b>\n"]

    # Время до сброса
    now = datetime.now(timezone.utc)
    next_reset = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if next_reset <= now:
        from datetime import timedelta
        next_reset = next_reset + timedelta(days=1)
    remaining = int((next_reset - now).total_seconds())
    h, m = divmod(remaining // 60, 60)
    lines.append(f"⏰ Сброс через: {h}ч {m}м\n")
    lines.append(f"{'─' * 22}\n")

    for quest in quests:
        cfg = QUESTS_BY_ID.get(quest.quest_id)
        if not cfg:
            continue

        pct = int(quest.progress / cfg.target * 100) if cfg.target > 0 else 0
        bar_filled = int(pct / 10)
        bar = "🟩" * bar_filled + "⬛" * (10 - bar_filled)

        if quest.is_claimed:
            status = "✅"
        elif quest.is_completed:
            status = "🎁"
        else:
            status = "🔄"

        lines.append(
            f"{status} {cfg.emoji} <b>{cfg.name}</b>\n"
            f"  {cfg.description}: {quest.progress}/{cfg.target}\n"
            f"  {bar} {pct}%\n"
            f"  💰 {fmt_num(cfg.reward_coins)}"
            + (f" | 🎟 +{cfg.reward_tickets}" if cfg.reward_tickets > 0 else "")
            + "\n"
        )

        if quest.is_completed and not quest.is_claimed:
            builder.row(InlineKeyboardButton(
                text=f"🎁 Забрать: {cfg.emoji} {cfg.name}",
                callback_data=f"quest_claim:{quest.quest_id}"
            ))

    builder.row(InlineKeyboardButton(
        text="🔄 Обновить", callback_data="daily_quests"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Главное меню", callback_data="main_menu"
    ))

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("quest_claim:"))
async def cb_quest_claim(cb: CallbackQuery, session: AsyncSession, user: User):
    quest_id = cb.data.split(":")[1]
    result = await quest_service.claim_reward(session, user, quest_id)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    msg = f"✅ Награда получена!\n💰 +{fmt_num(result['coins'])} NHCoin"
    if result["tickets"] > 0:
        msg += f"\n🎟 +{result['tickets']} тикетов"
    await cb.answer(msg, show_alert=True)
    await cb_daily_quests(cb, session, user)