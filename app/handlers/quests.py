from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from app.models.user import User
from app.services.quest_service import quest_service
from app.services.cooldown_service import cooldown_service
from app.constants.quests import QUESTS_BY_ID
from app.config.game_balance import QUEST_SWAP_COSTS, QUEST_SWAP_MAX_PER_DAY, QUEST_FULL_REROLL_COST
from app.utils.formatters import fmt_num

router = Router()

PAGE_SIZE = 5


def _fmt_millions(coins: int) -> str:
    m = coins // 1_000_000
    rest = coins % 1_000_000
    if rest == 0:
        return f"{m}M"
    return f"{m}.{rest // 100_000}M"


def _time_to_reset() -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    next_reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    remaining = int((next_reset - now).total_seconds())
    h, m = divmod(remaining // 60, 60)
    return h, m


# ── Главная страница квестов (без кнопок замены) ─────────────────────────────

def _build_quest_page(
    quests: list,
    page: int,
    h: int,
    m: int,
    swap_count: int,
    reroll_used: bool,
) -> tuple[str, "InlineKeyboardMarkup"]:
    regular = [q for q in quests if q.quest_id != "all_done"]
    all_done = next((q for q in quests if q.quest_id == "all_done"), None)

    total_pages = max(1, (len(regular) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    page_quests = regular[page * PAGE_SIZE: (page + 1) * PAGE_SIZE]

    swap_left = QUEST_SWAP_MAX_PER_DAY - swap_count
    next_swap_cost = QUEST_SWAP_COSTS[swap_count] if swap_count < QUEST_SWAP_MAX_PER_DAY else None

    lines = [
        "📋 <b>Ежедневные задания</b>\n",
        f"⏰ Сброс через: <b>{h}ч {m}м</b>",
        f"📄 Страница {page + 1}/{total_pages}",
        f"💸 Замен осталось: <b>{swap_left}/3</b>" + (
            f"  (след.: {_fmt_millions(next_swap_cost)})" if next_swap_cost else " — исчерпаны"
        ),
        ("♻️ Реролл: <b>доступен</b>" if not reroll_used else "♻️ Реролл: использован"),
        "\n" + "─" * 22 + "\n",
    ]

    builder = InlineKeyboardBuilder()

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

    # Задание «Выполнить все»
    if all_done:
        cfg_ad = QUESTS_BY_ID.get("all_done")
        if cfg_ad:
            pct_ad = int(all_done.progress / cfg_ad.target * 100) if cfg_ad.target > 0 else 0
            bar_ad = "🟨" * int(pct_ad / 10) + "⬛" * (10 - int(pct_ad / 10))
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

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"quests_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text="🔄 Обновить", callback_data=f"quests_page:{page}"))
    if (page + 1) * PAGE_SIZE < len(regular):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"quests_page:{page + 1}"))
    builder.row(*nav)

    builder.row(InlineKeyboardButton(
        text="♻️ Переролить награды",
        callback_data="quest_reroll_menu"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    return "\n".join(lines), builder.as_markup()


async def _show_quests(cb: CallbackQuery, session: AsyncSession, user: User, page: int = 0):
    quests = await quest_service.get_or_create_quests(session, user)
    swap_count = await quest_service.get_swap_count(user.id)
    reroll_used = await quest_service.is_reroll_used(user.id)
    h, m = _time_to_reset()
    text, markup = _build_quest_page(quests, page, h, m, swap_count, reroll_used)
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass


# ── Страница переролла ────────────────────────────────────────────────────────

async def _show_reroll_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    swap_count = await quest_service.get_swap_count(user.id)
    reroll_used = await quest_service.is_reroll_used(user.id)
    swap_left = QUEST_SWAP_MAX_PER_DAY - swap_count
    next_swap_cost = QUEST_SWAP_COSTS[swap_count] if swap_count < QUEST_SWAP_MAX_PER_DAY else None
    h, m = _time_to_reset()

    lines = [
        "♻️ <b>Переролить награды</b>\n",
        f"⏰ Сброс через: <b>{h}ч {m}м</b>",
        f"💸 Замен осталось: <b>{swap_left}/3</b>",
    ]
    for i, cost in enumerate(QUEST_SWAP_COSTS):
        mark = "✅" if swap_count > i else ("➡️" if swap_count == i else "🔒")
        lines.append(f"  {mark} Замена {i + 1}: {_fmt_millions(cost)}")

    lines += [
        "",
        f"♻️ Полный реролл: {_fmt_millions(QUEST_FULL_REROLL_COST)}"
        + (" ✅ использован" if reroll_used else " (доступен)"),
    ]

    builder = InlineKeyboardBuilder()
    if next_swap_cost:
        builder.row(InlineKeyboardButton(
            text=f"💸 Заменить задание ({_fmt_millions(next_swap_cost)})",
            callback_data="quest_swap_select"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="💸 Замены исчерпаны на сегодня",
            callback_data="noop_quest"
        ))

    if not reroll_used:
        builder.row(InlineKeyboardButton(
            text=f"♻️ Переролить всё ({_fmt_millions(QUEST_FULL_REROLL_COST)})",
            callback_data="quest_full_reroll"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="♻️ Реролл уже использован",
            callback_data="noop_quest"
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="daily_quests"))

    try:
        await cb.message.edit_text("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass


# ── Выбор задания для замены ──────────────────────────────────────────────────

async def _show_swap_select(cb: CallbackQuery, session: AsyncSession, user: User):
    quests = await quest_service.get_or_create_quests(session, user)
    swap_count = await quest_service.get_swap_count(user.id)
    next_swap_cost = QUEST_SWAP_COSTS[swap_count] if swap_count < QUEST_SWAP_MAX_PER_DAY else None

    swappable = [
        q for q in quests
        if q.quest_id != "all_done" and not q.is_completed and not q.is_claimed
    ]

    builder = InlineKeyboardBuilder()
    lines = [
        f"💸 <b>Какое задание заменить?</b>",
        f"Стоимость: <b>{_fmt_millions(next_swap_cost)}</b>\n",
    ]

    for quest in swappable:
        cfg = QUESTS_BY_ID.get(quest.quest_id)
        if not cfg:
            continue
        pct = int(quest.progress / cfg.target * 100) if cfg.target > 0 else 0
        lines.append(f"  {cfg.emoji} {cfg.name} — {quest.progress}/{cfg.target} ({pct}%)")
        builder.row(InlineKeyboardButton(
            text=f"{cfg.emoji} {cfg.name}",
            callback_data=f"quest_swap:{quest.quest_id}"
        ))

    if not swappable:
        lines.append("Нет заданий для замены (все выполнены или уже заменены)")

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="quest_reroll_menu"))

    try:
        await cb.message.edit_text("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass


# ── Хендлеры ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "daily_quests")
async def cb_daily_quests(cb: CallbackQuery, session: AsyncSession, user: User):
    await _show_quests(cb, session, user, page=0)


@router.callback_query(F.data.startswith("quests_page:"))
async def cb_quests_page(cb: CallbackQuery, session: AsyncSession, user: User):
    page = int(cb.data.split(":")[1])
    await _show_quests(cb, session, user, page=page)


@router.callback_query(F.data == "quest_reroll_menu")
async def cb_quest_reroll_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    await _show_reroll_menu(cb, session, user)
    await cb.answer()


@router.callback_query(F.data == "quest_swap_select")
async def cb_quest_swap_select(cb: CallbackQuery, session: AsyncSession, user: User):
    swap_count = await quest_service.get_swap_count(user.id)
    if swap_count >= QUEST_SWAP_MAX_PER_DAY:
        await cb.answer("Замены исчерпаны на сегодня", show_alert=True)
        return
    await _show_swap_select(cb, session, user)
    await cb.answer()


@router.callback_query(F.data.startswith("quest_claim:"))
async def cb_quest_claim(cb: CallbackQuery, session: AsyncSession, user: User):
    quest_id = cb.data.split(":")[1]
    result = await quest_service.claim_reward(session, user, quest_id)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    from app.utils.region_activity import record
    await record(session, user.id, "quest")

    msg = f"✅ Награда получена!\n💰 +{fmt_num(result['coins'])} NHCoin"
    if result["tickets"] > 0:
        msg += f"\n🎟 +{result['tickets']} тикетов"
    await cb.answer(msg, show_alert=True)
    await _show_quests(cb, session, user, page=0)


@router.callback_query(F.data.startswith("quest_swap:"))
async def cb_quest_swap(cb: CallbackQuery, session: AsyncSession, user: User):
    lock_key = f"lock:quest_swap:{user.id}"
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подождите...", show_alert=False)
        return

    quest_id = cb.data.split(":")[1]
    result = await quest_service.swap_quest(session, user, quest_id)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    await cb.answer(
        f"✅ Задание заменено!\n💰 -{fmt_num(result['cost'])} NHCoin",
        show_alert=True,
    )
    await _show_reroll_menu(cb, session, user)


@router.callback_query(F.data == "quest_full_reroll")
async def cb_quest_full_reroll(cb: CallbackQuery, session: AsyncSession, user: User):
    lock_key = f"lock:quest_reroll:{user.id}"
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подождите...", show_alert=False)
        return

    result = await quest_service.full_reroll(session, user)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    await cb.answer(
        f"♻️ Задания переролены ({result['replaced']} шт.)!\n"
        f"💰 -{fmt_num(result['cost'])} NHCoin",
        show_alert=True,
    )
    await _show_quests(cb, session, user, page=0)


@router.callback_query(F.data == "noop_quest")
async def cb_noop_quest(cb: CallbackQuery):
    await cb.answer()
