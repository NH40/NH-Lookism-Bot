"""Чёрный рынок — эксклюзивный раздел для VVIP игроков (круговые донаты)."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.data.titles import CIRCULAR_DONATS, CIRCULAR_DONAT_MAP, CLAN_DONAT_ITEMS, MANAGER_USERNAME

router = Router()


async def _vvip_check(session, user: User) -> bool:
    """VVIP = купил все 5 донатных сетов титулов. 1 запрос вместо 5."""
    from app.repositories.title_repo import title_repo
    return await title_repo.has_all_sets(session, user.id)


@router.callback_query(F.data == "black_market")
async def cb_black_market(cb: CallbackQuery, session: AsyncSession, user: User):
    if not await _vvip_check(session, user):
        await cb.answer("🔒 Только для VVIP (нужны все 5 донатных сетов)", show_alert=True)
        return

    from app.services.circular_donat_service import get_user_circles
    circles_map = await get_user_circles(session, user.id)

    builder = InlineKeyboardBuilder()
    for d in CIRCULAR_DONATS:
        n = circles_map.get(d.donat_id, 0)
        suffix = f" [{n}/{d.max_circles}]" if n else ""
        builder.row(InlineKeyboardButton(
            text=f"{d.emoji} {d.name}{suffix} — {d.price_per_circle}₽/круг",
            callback_data=f"bm_detail:{d.donat_id}",
        ))
    builder.row(InlineKeyboardButton(
        text="🏛 Клановые привилегии", callback_data="bm_clan_donats"
    ))
    builder.row(InlineKeyboardButton(
        text=f"💬 Купить у менеджера",
        url=f"https://t.me/{MANAGER_USERNAME.lstrip('@')}",
    ))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    # Суммарный пассивный доход от кругов (со всеми % баффами дохода)
    passive = getattr(user, "circ_passive_income", 0)
    passive_line = ""
    if passive:
        from app.services.business_service import business_service as _bs
        from app.utils.formatters import fmt_num as _fn
        info = await _bs.get_income_breakdown(session, user)
        base_per_min = passive  # уже в NHCoin/мин
        eff_per_min  = info.get("circ_passive_per_min", base_per_min)
        all_pct      = info.get("total_bonus_percent", 0) + info.get("potion_bonus", 0)
        if all_pct and eff_per_min != base_per_min:
            passive_line = (
                f"\n💸 Пассивный доход: +{_fn(eff_per_min)}/мин"
                f" (с баффами +{all_pct}%, базово {_fn(base_per_min)}/мин)"
            )
        else:
            passive_line = f"\n💸 Пассивный доход: +{_fn(eff_per_min)}/мин"

    try:
        await cb.message.edit_text(
            f"🖤 <b>Чёрный рынок</b>\n"
            f"<i>Эксклюзивный раздел для обладателей всех донатных сетов</i>"
            f"{passive_line}\n\n"
            f"🔄 <b>Круговые донаты</b> — покупай круги и получай перманентные баффы.\n"
            f"Каждый новый круг суммируется с предыдущими.\n\n"
            f"Выберите донат для просмотра:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("bm_detail:"))
async def cb_bm_detail(cb: CallbackQuery, session: AsyncSession, user: User):
    if not await _vvip_check(session, user):
        await cb.answer("🔒 Только для VVIP", show_alert=True)
        return

    donat_id = cb.data.split(":")[1]
    d = CIRCULAR_DONAT_MAP.get(donat_id)
    if not d:
        await cb.answer("Донат не найден", show_alert=True)
        return

    from app.services.circular_donat_service import get_user_circles
    circles_map = await get_user_circles(session, user.id)
    my_circles = circles_map.get(donat_id, 0)

    nh_donate = user.nh_donate or 0
    lines = [
        f"{d.emoji} <b>{d.name}</b>\n",
        f"🔄 Ваши круги: <b>{my_circles}/{d.max_circles}</b>",
        f"💰 Цена круга: <b>{d.price_per_circle} NHDonate</b> | MAX: {d.price_per_circle * d.max_circles} NHD\n",
        f"🪙 Ваш баланс NHDonate: <b>{nh_donate:,}</b>\n",
        f"🎁 <b>Бонус за каждый круг:</b>",
        f"  {d.circle_bonus}\n",
    ]

    if d.special_bonuses:
        lines.append("⭐ <b>Особые бонусы за круги:</b>")
        for circle_n, bonus_desc in d.special_bonuses:
            mark = "✅" if my_circles >= circle_n else "🔒"
            lines.append(f"  {mark} Круг {circle_n}: {bonus_desc}")

    builder = InlineKeyboardBuilder()

    if my_circles < d.max_circles:
        can_afford = "✅" if nh_donate >= d.price_per_circle else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can_afford} Купить круг {my_circles + 1} — {d.price_per_circle} NHDonate",
            callback_data=f"bm_buy_circle:{donat_id}",
        ))

    builder.row(InlineKeyboardButton(
        text="💳 Пополнить NHDonate", callback_data="donate_topup"
    ))
    builder.row(InlineKeyboardButton(text="◀️ К чёрному рынку", callback_data="black_market"))

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("bm_buy_circle:"))
async def cb_bm_buy_circle(cb: CallbackQuery, session: AsyncSession, user: User):
    """Покупка 1 круга кругового доната за NHDonate."""
    if not await _vvip_check(session, user):
        await cb.answer("🔒 Только для VVIP", show_alert=True)
        return

    donat_id = cb.data.split(":")[1]
    d = CIRCULAR_DONAT_MAP.get(donat_id)
    if not d:
        await cb.answer("Донат не найден", show_alert=True)
        return

    nh_donate = user.nh_donate or 0
    if nh_donate < d.price_per_circle:
        await cb.answer(
            f"❌ Недостаточно NHDonate!\n"
            f"Нужно: {d.price_per_circle} · У вас: {nh_donate}\n\n"
            f"Пополните баланс через /donate",
            show_alert=True,
        )
        return

    # Антидабл-лок
    from app.services.cooldown_service import cooldown_service
    lock_key = f"bm_buy_circle:{user.id}:{donat_id}"
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подождите...", show_alert=False)
        return

    from app.services.circular_donat_service import add_circle
    result = await add_circle(session, user, donat_id)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    user.nh_donate = nh_donate - d.price_per_circle
    await session.commit()

    await cb.answer(
        f"✅ {d.emoji} {d.name}: круг {result['circles']}/{d.max_circles} куплен!\n"
        f"Остаток NHDonate: {user.nh_donate}",
        show_alert=True,
    )
    # Перерисовываем страницу доната
    await cb_bm_detail(cb, session, user)


@router.callback_query(F.data == "bm_clan_donats")
async def cb_bm_clan_donats(cb: CallbackQuery, session: AsyncSession, user: User):
    if not await _vvip_check(session, user):
        await cb.answer("🔒 Только для VVIP", show_alert=True)
        return

    from app.constants.clan import CLAN_DONAT_PACKAGES, MAX_DONAT_CIRCLES

    lines = [
        "🏛 <b>Клановые донаты</b>\n",
        "<i>Каждый пакет можно купить до 5 раз. Бонусы накапливаются.</i>\n",
        "<b>Доступные пакеты:</b>",
    ]
    for pkg in CLAN_DONAT_PACKAGES:
        bonuses = []
        if pkg.income_pct:  bonuses.append(f"+{pkg.income_pct}% к доходу")
        if pkg.ticket_pct:  bonuses.append(f"+{pkg.ticket_pct}% к тикетам")
        if pkg.train_pct:   bonuses.append(f"+{pkg.train_pct}% к тренировке")
        lines.append(f"\n{pkg.name} — <b>{pkg.price_rub}₽</b> (макс {MAX_DONAT_CIRCLES} кругов)")
        lines.append(f"  {', '.join(bonuses)}")

    lines.append(f"\n✍️ Для оформления напишите менеджеру")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"💬 Купить у {MANAGER_USERNAME}",
        url=f"https://t.me/{MANAGER_USERNAME.lstrip('@')}",
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="black_market"))

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()
