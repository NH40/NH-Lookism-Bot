from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from app.models.user import User
from app.services.quest_service import quest_service
from app.constants.quests import QUESTS_BY_ID
from app.utils.formatters import fmt_num

router = Router()

# Заданий на странице (кроме all_done, который всегда снизу)
PAGE_SIZE = 5


def _build_quest_page(
    quests: list,
    page: int,
    h: int,
    m: int,
) -> tuple[str, "InlineKeyboardMarkup"]:
    """Формирует текст и клавиатуру для страницы заданий."""
    # Разделяем all_done и обычные задания
    regular = [q for q in quests if q.quest_id != "all_done"]
    all_done = next((q for q in quests if q.quest_id == "all_done"), None)

    total_pages = max(1, (len(regular) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    page_quests = regular[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    lines = [
        "📋 <b>Ежедневные задания</b>\n",
        f"⏰ Сброс через: <b>{h}ч {m}м</b>",
        f"📄 Страница {page + 1}/{total_pages}\n",
        "─" * 22 + "\n",
    ]

    builder = InlineKeyboardBuilder()

    # ── Обычные задания текущей страницы ─────────────────────────────────────
    for quest in page_quests:
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

        reward = f"💰 {fmt_num(cfg.reward_coins)}"
        if cfg.reward_tickets > 0:
            reward += f" | 🎟 +{cfg.reward_tickets}"

        lines.append(
            f"{status} {cfg.emoji} <b>{cfg.name}</b>\n"
            f"  {cfg.description}: {quest.progress}/{cfg.target}\n"
            f"  {bar} {pct}%\n"
            f"  {reward}\n"
        )

        if quest.is_completed and not quest.is_claimed:
            builder.row(InlineKeyboardButton(
                text=f"🎁 {cfg.emoji} {cfg.name}",
                callback_data=f"quest_claim:{quest.quest_id}"
            ))

    # ── Разделитель и задание «Выполнить все» ────────────────────────────────
    if all_done:
        cfg_ad = QUESTS_BY_ID.get("all_done")
        if cfg_ad:
            pct_ad = int(all_done.progress / cfg_ad.target * 100) if cfg_ad.target > 0 else 0
            bar_ad_filled = int(pct_ad / 10)
            bar_ad = "🟨" * bar_ad_filled + "⬛" * (10 - bar_ad_filled)

            if all_done.is_claimed:
                status_ad = "✅"
            elif all_done.is_completed:
                status_ad = "🎁"
            else:
                status_ad = "⭐"

            lines.append("─" * 22 + "\n")
            lines.append(
                f"{status_ad} {cfg_ad.emoji} <b>{cfg_ad.name}</b>\n"
                f"  {cfg_ad.description}: {all_done.progress}/{cfg_ad.target}\n"
                f"  {bar_ad} {pct_ad}%\n"
                f"  💰 {fmt_num(cfg_ad.reward_coins)} | 🎟 +{cfg_ad.reward_tickets}\n"
            )
            if all_done.is_completed and not all_done.is_claimed:
                builder.row(InlineKeyboardButton(
                    text="🎁 🌟 Мастер на все руки",
                    callback_data="quest_claim:all_done"
                ))

    # ── Навигация ─────────────────────────────────────────────────────────────
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="◀️", callback_data=f"quests_page:{page - 1}"
        ))
    nav_buttons.append(InlineKeyboardButton(
        text="🔄 Обновить", callback_data=f"quests_page:{page}"
    ))
    if (page + 1) * PAGE_SIZE < len(regular):
        nav_buttons.append(InlineKeyboardButton(
            text="▶️", callback_data=f"quests_page:{page + 1}"
        ))
    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(
        text="◀️ Главное меню", callback_data="main_menu"
    ))

    return "\n".join(lines), builder.as_markup()


async def _show_quests(cb: CallbackQuery, session: AsyncSession, user: User, page: int = 0):
    quests = await quest_service.get_or_create_quests(session, user)

    now = datetime.now(timezone.utc)
    next_reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    remaining = int((next_reset - now).total_seconds())
    h, m = divmod(remaining // 60, 60)

    text, markup = _build_quest_page(quests, page, h, m)
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data == "daily_quests")
async def cb_daily_quests(cb: CallbackQuery, session: AsyncSession, user: User):
    await _show_quests(cb, session, user, page=0)


@router.callback_query(F.data.startswith("quests_page:"))
async def cb_quests_page(cb: CallbackQuery, session: AsyncSession, user: User):
    page = int(cb.data.split(":")[1])
    await _show_quests(cb, session, user, page=page)


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
    await _show_quests(cb, session, user, page=0)
