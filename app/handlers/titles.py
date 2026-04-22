from aiogram import Router, F
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

@router.callback_query(F.data == "achievements_menu")
async def cb_achievements_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    result = await session.execute(
        select(UserAchievement.achievement_id).where(
            UserAchievement.user_id == user.id,
            UserAchievement.claimed == True,
        )
    )
    claimed = set(result.scalars().all())

    categories = [
        ("⚔️ Боевая мощь",  ["power_10k", "power_50k", "power_100k", "power_1m"]),
        ("📍 Фазы",          ["first_king", "first_fist", "fist_10_cities", "emperor"]),
        ("🏆 Топ",           ["top_10", "top_5", "top_1"]),
        ("💸 Траты",         ["spend_100k", "spend_1m"]),
        ("⚔️ Победы",        ["wins_10", "wins_100"]),
        ("🏛 Аукцион",       ["auction_win_1", "auction_win_5"]),
        ("📦 Коллекция",     ["all_achievements", "absolute"]),
        ("🔐 Секретные",     ["settings_100", "settings_500", "future_masterpiece", "shadow_syndicate"]),
    ]

    lines = []
    for cat_name, ids in categories:
        lines.append(f"\n{cat_name}")
        for aid in ids:
            ach = ACHIEVEMENT_MAP.get(aid)
            if not ach:
                continue
            if ach.secret and aid not in claimed:
                lines.append("  ❓ ???")
                continue
            status = "✅" if aid in claimed else "⬜"
            lines.append(
                f"  {status} {ach.name}\n"
                f"    └ {ach.description}\n"
                f"    └ 🎁 {ach.bonus_description}"
            )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔍 Проверить достижения", callback_data="check_achievements"
    ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="titles"))

    await cb.message.edit_text(
        f"🥇 <b>Достижения</b>\n{''.join(lines)}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


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

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=back_kb("achievements_menu"),
        parse_mode="HTML",
    )


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

    lines = []
    for s in DONAT_SETS:
        titles_in_set = [t for t in DONAT_TITLES if t.set_id == s.set_id]
        owned_in_set = [t for t in titles_in_set if t.title_id in owned_titles]
        is_full = len(owned_in_set) == len(titles_in_set)
        status = "✅" if is_full else f"{len(owned_in_set)}/{len(titles_in_set)}"

        lines.append(
            f"✨ <b>{s.name}</b> [{status}] — {s.price_rub}₽\n"
            f"  {s.set_bonus}"
        )
        builder.button(
            text=f"📦 {s.name} — {s.price_rub}₽",
            callback_data=f"donat_set_detail:{s.set_id}"
        )

    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text=f"💬 Написать менеджеру", url=f"https://t.me/{MANAGER_USERNAME.lstrip('@')}"
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

    lines = [
        f"📦 <b>{s.name}</b>\n",
        f"🎁 Бонус сета: {s.set_bonus}",
        f"💰 Цена сета: {s.price_rub}₽\n",
        f"Состав сета ({owned_count}/{len(titles_in_set)}):",
    ]
    for t in titles_in_set:
        is_owned = t.title_id in owned_titles
        status = "✅" if is_owned else "❌"
        lines.append(
            f"  {status} {t.emoji} {t.name} — {t.price_rub}₽\n"
            f"    {t.bonus_description}"
        )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"💬 Для покупки: {MANAGER_USERNAME}",
        url=f"https://t.me/{MANAGER_USERNAME.lstrip('@')}"
    ))
    builder.row(InlineKeyboardButton(text="🔙 К сетам", callback_data="donat_sets_menu"))

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )