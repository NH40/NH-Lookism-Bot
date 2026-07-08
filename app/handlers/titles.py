from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.title import UserDonatTitle, UserAchievement
from app.utils.keyboards import back_kb
from app.utils.formatters import fmt_num
from app.data.titles import (
    ACHIEVEMENTS, ACHIEVEMENT_MAP,
    DONAT_SETS, DONAT_SET_MAP, DONAT_TITLES, DONAT_TITLE_MAP,
    MANAGER_USERNAME,
)

router = Router()


@router.callback_query(F.data == "titles")
async def cb_titles(cb: CallbackQuery, session: AsyncSession, user: User):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🥇 Достижения",   callback_data="achievements_menu"))
    builder.row(InlineKeyboardButton(text="💎 Донатные сеты", callback_data="donat_sets_menu"))
    builder.row(InlineKeyboardButton(text="🔙 Назад",         callback_data="main_menu"))

    await cb.message.edit_text(
        "🏆 <b>Титулы</b>\n\n"
        "🥇 Достижения — выполняй задачи и получай бонусы\n"
        "💎 Донатные сеты — особые привилегии за поддержку проекта",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


# ── ДОСТИЖЕНИЯ ──────────────────────────────────────────────────────────────

_ACH_CATEGORIES = [
    ("⚔️ Боевая мощь",  ["power_10k", "power_50k", "power_100k", "power_500k", "power_1m"]),
    ("📍 Фазы",          ["first_king", "king_5_cities", "first_fist", "fist_10_cities", "emperor"]),
    ("🌟 Престиж",       ["prestige_1", "prestige_3"]),
    ("🏆 Топ",           ["top_10", "top_5", "top_1"]),
    ("💸 Траты",         ["spend_100k", "spend_1m", "spend_5m"]),
    ("⚔️ Победы",        ["wins_10", "wins_100", "wins_500", "wins_1000"]),
    ("🏛 Аукцион",       ["auction_win_1", "auction_win_5"]),
    ("👹 Рейды",         ["raid_boss_1", "raid_boss_10", "raid_boss_100"]),
    ("🪖 Армия",         ["army_100k", "army_1m"]),
    ("🌀 Путь и УИ",     ["path_max", "ui_master", "med_genius_master"]),
    ("📋 Задания",       ["quests_100", "quests_500", "quests_1000"]),
    ("💱 Биржа",         ["market_10", "market_100"]),
    ("🎯 Особые",        ["future_masterpiece", "shadow_syndicate"]),
    ("📦 Коллекция",     ["collect_rank_complete", "all_achievements", "absolute"]),
    ("🔐 Секретные",     ["settings_100", "settings_500"]),
]
_ACH_PAGE_SIZE = 5  # категорий на странице


async def _show_achievements(cb: CallbackQuery, session, user: User, page: int = 0):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    result = await session.execute(
        select(UserAchievement.achievement_id).where(
            UserAchievement.user_id == user.id,
            UserAchievement.claimed == True,
        )
    )
    claimed = set(result.scalars().all())

    total_pages = max(1, (len(_ACH_CATEGORIES) + _ACH_PAGE_SIZE - 1) // _ACH_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    page_cats = _ACH_CATEGORIES[page * _ACH_PAGE_SIZE : (page + 1) * _ACH_PAGE_SIZE]

    lines = []
    for cat_name, ids in page_cats:
        lines.append(f"\n<b>{cat_name}</b>\n")
        for aid in ids:
            ach = ACHIEVEMENT_MAP.get(aid)
            if not ach:
                continue
            if ach.secret and aid not in claimed:
                lines.append("  ❓ ???\n")
                continue
            status = "✅" if aid in claimed else "⬜"
            lines.append(
                f"  {status} {ach.name}\n"
                f"    └ {ach.description}\n"
                f"    └ 🎁 {ach.bonus_description}\n"
            )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔍 Проверить достижения", callback_data="check_achievements"
    ))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"ach_page:{page - 1}"))
    nav.append(InlineKeyboardButton(
        text=f"📄 {page + 1}/{total_pages}", callback_data=f"ach_page:{page}"
    ))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"ach_page:{page + 1}"))
    builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="titles"))

    try:
        await cb.message.edit_text(
            f"🥇 <b>Достижения</b> (стр. {page + 1}/{total_pages})\n{''.join(lines)}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "achievements_menu")
async def cb_achievements_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    await _show_achievements(cb, session, user, page=0)


@router.callback_query(F.data.startswith("ach_page:"))
async def cb_ach_page(cb: CallbackQuery, session: AsyncSession, user: User):
    page = int(cb.data.split(":")[1])
    await _show_achievements(cb, session, user, page=page)


@router.callback_query(F.data == "check_achievements")
async def cb_check_achievements(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.title_service import title_service
    granted = await title_service.check_achievements(session, user)
    if not granted:
        await cb.answer("Новых достижений нет", show_alert=True)
        return

    lines = ["🎉 <b>Новые достижения!</b>\n"]
    total_coins = 0
    for g in granted:
        lines.append(f"✅ {g['name']}\n  └ {g['bonus_description']}")
        total_coins += g.get("coins", 0)

    if total_coins:
        lines.append(f"\n💰 Итого монет: +{fmt_num(total_coins)}")

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=back_kb("achievements_menu"),
            parse_mode="HTML",
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# ── ДОНАТНЫЕ СЕТЫ ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "donat_sets_menu")
async def cb_donat_sets_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    # Получаем все титулы пользователя
    result = await session.execute(
        select(UserDonatTitle.title_id).where(UserDonatTitle.user_id == user.id)
    )
    owned_titles = set(result.scalars().all())

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()

    nh_donate = user.nh_donate or 0
    lines = [f"🪙 Баланс NHDonate: <b>{fmt_num(nh_donate)}</b>\n"]
    for s in DONAT_SETS:
        titles_in_set = [t for t in DONAT_TITLES if t.set_id == s.set_id]
        owned_in_set = [t for t in titles_in_set if t.title_id in owned_titles]
        is_full = len(owned_in_set) == len(titles_in_set)
        status = "✅" if is_full else f"{len(owned_in_set)}/{len(titles_in_set)}"

        lines.append(
            f"✨ <b>{s.name}</b> [{status}]\n"
            f"  {s.set_bonus}"
        )
        builder.button(
            text=f"📦 {s.name} [{status}]",
            callback_data=f"donat_set_detail:{s.set_id}"
        )

    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="💳 Пополнить NHDonate", callback_data="donate_topup"
    ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="titles"))

    await cb.message.edit_text(
        "💎 <b>Донатные сеты</b>\n\n" + "\n\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("donat_set_detail:"))
async def cb_donat_set_detail(cb: CallbackQuery, session: AsyncSession, user: User):
    set_id = cb.data.split(":")[1]
    s = DONAT_SET_MAP.get(set_id)
    if not s:
        await cb.answer("Сет не найден", show_alert=True)
        return

    result = await session.execute(
        select(UserDonatTitle.title_id).where(UserDonatTitle.user_id == user.id)
    )
    owned_titles = set(result.scalars().all())

    titles_in_set = [t for t in DONAT_TITLES if t.set_id == set_id]
    owned_count = sum(1 for t in titles_in_set if t.title_id in owned_titles)
    nh_donate = user.nh_donate or 0

    unowned_titles = [t for t in titles_in_set if t.title_id not in owned_titles]

    lines = [
        f"📦 <b>{s.name}</b>\n",
        f"🎁 Бонус сета: {s.set_bonus}\n",
        f"🪙 Ваш баланс NHDonate: <b>{fmt_num(nh_donate)}</b>\n",
    ]

    if not unowned_titles:
        lines.append(f"✅ <b>Все титулы сета куплены!</b> ({len(titles_in_set)}/{len(titles_in_set)})")
    else:
        lines.append(f"🛒 <b>Доступно к покупке</b> ({owned_count}/{len(titles_in_set)} куплено):")
        for t in unowned_titles:
            can_afford = "✅" if nh_donate >= t.price_rub else "❌"
            lines.append(
                f"  {can_afford} {t.emoji} {t.name} — <b>{t.price_rub} NHDonate</b>\n"
                f"    {t.bonus_description}"
            )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()

    # Кнопки покупки только для неприобретённых титулов
    for t in unowned_titles:
        can_afford = "✅" if nh_donate >= t.price_rub else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can_afford} {t.emoji} {t.name} — {t.price_rub} NHDonate",
            callback_data=f"buy_title:{t.title_id}",
        ))

    builder.row(InlineKeyboardButton(
        text="💳 Пополнить NHDonate", callback_data="donate_topup"
    ))
    builder.row(InlineKeyboardButton(text="🔙 К сетам", callback_data="donat_sets_menu"))

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("buy_title:"))
async def cb_buy_title(cb: CallbackQuery, session: AsyncSession, user: User):
    """Покупка донатного титула за NHDonate."""
    title_id = cb.data.split(":")[1]
    from app.data.titles import DONAT_TITLE_MAP
    cfg = DONAT_TITLE_MAP.get(title_id)
    if not cfg:
        await cb.answer("Титул не найден", show_alert=True)
        return

    nh_donate = user.nh_donate or 0
    if nh_donate < cfg.price_rub:
        await cb.answer(
            f"❌ Недостаточно NHDonate!\n"
            f"Нужно: {cfg.price_rub} · У вас: {nh_donate}\n\n"
            f"Пополните баланс через /donate",
            show_alert=True,
        )
        return

    # Антидабл-лок через cooldown_service
    from app.services.cooldown_service import cooldown_service
    lock_key = f"buy_title:{user.id}:{title_id}"
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подождите...", show_alert=False)
        return

    from app.services.title_service import title_service
    result = await title_service.grant_title(session, user, title_id)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    user.nh_donate = nh_donate - cfg.price_rub
    await session.commit()

    await cb.answer(
        f"✅ Титул «{cfg.emoji} {cfg.name}» получен!\n"
        f"Остаток NHDonate: {user.nh_donate}",
        show_alert=True,
    )
    # Перерисовываем страницу сета
    await cb_donat_set_detail(cb, session, user)