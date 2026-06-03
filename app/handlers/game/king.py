from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.city import District
from app.services.game_service import game_service
from app.services.cooldown_service import cooldown_service
from app.repositories.city_repo import city_repo
from app.repositories.user_repo import user_repo
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num, fmt_ttl
from app.utils.truce import truce_button_label
import html

router = Router()


async def build_king_menu(session, user, page: int = 0):
    cd_key = cooldown_service.attack_key(user.id)
    cd = await cooldown_service.get_ttl(cd_key)

    cities = await city_repo.get_available_king_cities(session, user.sector or "Н")

    from app.models.city import City
    from app.data.cities import KING_DISTRICT_BASE_POWER

    # ── Query 1: count of distinct cities user owns (for 9/10 warning) ──────
    my_cities_count = await session.scalar(
        select(func.count(func.distinct(District.city_id)))
        .join(City, City.id == District.city_id)
        .where(
            District.owner_id == user.id,
            District.is_captured == True,
            City.phase != "fist",
        )
    ) or 0

    if not cities:
        eligible = []
    else:
        city_ids = [c.id for c in cities]
        cities_by_id = {c.id: c for c in cities}

        # ── Query 2: district counts for ALL cities in one aggregated query ─
        counts_r = await session.execute(
            select(
                District.city_id,
                func.count(District.id).filter(
                    District.owner_id == user.id,
                    District.is_captured == True,
                ).label("my_count"),
                func.count(District.id).filter(
                    District.is_captured == False,
                    District.owner_id == None,
                ).label("free_count"),
                func.count(District.id).filter(
                    District.is_captured == True,
                    District.owner_id != user.id,
                    District.owner_id != None,
                ).label("not_mine"),
            )
            .where(District.city_id.in_(city_ids))
            .group_by(District.city_id)
        )
        counts = {row.city_id: row for row in counts_r}

        # Eligible cities: have something to attack (free districts OR stealable non-fist districts)
        # Фильтр Кулак-заблокированных городов применяется ниже после загрузки фаз защитников
        eligible_ids = [
            cid for cid, row in counts.items()
            if (row.free_count or 0) > 0 or (row.not_mine or 0) > 0
        ]

        # ── Query 3: dominant player per eligible city (single query) ────────
        dominant_by_city: dict[int, int] = {}
        if eligible_ids:
            dom_subq = (
                select(
                    District.city_id.label("cid"),
                    District.owner_id.label("oid"),
                    func.count(District.id).label("cnt"),
                )
                .where(
                    District.city_id.in_(eligible_ids),
                    District.is_captured == True,
                    District.owner_id != None,
                    District.owner_id != user.id,
                )
                .group_by(District.city_id, District.owner_id)
                .order_by(District.city_id, func.count(District.id).desc())
                .subquery()
            )
            dom_rows = (await session.execute(
                select(dom_subq.c.cid, dom_subq.c.oid)
            )).all()
            for row in dom_rows:
                if row.cid not in dominant_by_city:
                    dominant_by_city[row.cid] = row.oid

        # ── Query 4: load all dominant users in one batch ────────────────────
        defender_ids = list(set(dominant_by_city.values()))
        defenders: dict[int, User] = {}
        if defender_ids:
            def_rows = (await session.execute(
                select(User.id, User.combat_power, User.phase)
                .where(User.id.in_(defender_ids))
            )).all()
            defenders = {row.id: row for row in def_rows}

        # ── Build eligible list (pure Python, no more DB calls) ──────────────
        eligible = []
        for city in cities:
            cid = city.id
            row = counts.get(cid)
            if row and (row.free_count or 0) == 0 and (row.not_mine or 0) == 0:
                continue

            dominant_id = dominant_by_city.get(cid)
            defender = defenders.get(dominant_id) if dominant_id else None

            # Пропускаем города, где все чужие районы принадлежат Кулаку и свободных нет
            if (
                defender and getattr(defender, 'phase', None) == "fist"
                and (row.free_count or 0) == 0
            ):
                continue

            if defender and defender.phase == "king":
                def_power = int(defender.combat_power or 0)
                can = "✅" if user.combat_power >= def_power else "❌"
                def_str = f"👤 {can} {fmt_num(def_power)}"
            else:
                bot_power = int(KING_DISTRICT_BASE_POWER * city.total_districts * city.district_power_multiplier)
                can = "✅" if user.combat_power >= bot_power else "❌"
                def_str = f"🤖 {can} {fmt_num(bot_power)}"

            type_id = city.type_id or 1
            my_in_city = (row.my_count if row else 0) or 0
            my_str = f"[моих:{my_in_city}] " if my_in_city > 0 else ""
            size_emoji = {1: "🏘", 2: "🏙", 3: "🌆", 4: "🌇", 5: "🌃"}.get(type_id, "🏙")
            eligible.append((city, size_emoji, my_str, def_str))

    # Пагинация
    per_page = 10
    total = len(eligible)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_items = eligible[page * per_page:(page + 1) * per_page]

    builder = InlineKeyboardBuilder()

    # Кнопка «Продолжить» — город с наибольшим прогрессом захвата у игрока
    if eligible and cities_by_id:
        best_city_id = None
        best_pct = -1
        for city, *_ in eligible:
            row = counts.get(city.id)
            my = (row.my_count if row else 0) or 0
            if my > 0:
                total = city.total_districts or 1
                pct = my / total
                if pct > best_pct:
                    best_pct = pct
                    best_city_id = city.id
                    best_city_name = city.name
        if best_city_id:
            pct_int = min(int(best_pct * 100), 99)
            builder.row(InlineKeyboardButton(
                text=f"⚡ Продолжить захват: {best_city_name} ({pct_int}%)",
                callback_data=f"king_city_info:{best_city_id}",
            ))

    for city, size_emoji, my_str, def_str in page_items:
        builder.row(InlineKeyboardButton(
            text=f"{size_emoji} {city.name} {my_str}| {def_str}",
            callback_data=f"king_city_info:{city.id}"
        ))

    nav = []
    if page >= 5:
        nav.append(InlineKeyboardButton(text="⏮ -5", callback_data=f"king_page:{page - 5}"))
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"king_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"king_page:{page + 1}"))
    if page + 5 < total_pages:
        nav.append(InlineKeyboardButton(text="+5 ⏭", callback_data=f"king_page:{page + 5}"))
    if nav:
        builder.row(*nav)

    cities_count = my_cities_count
    if cities_count >= 9:
        builder.row(InlineKeyboardButton(
            text=f"⚠️ {cities_count}/10 — последний город не через ботов!",
            callback_data="king_bots_menu"
        ))
    else:
        builder.row(InlineKeyboardButton(text="🤖 Боты-короли", callback_data="king_bots_menu"))
    builder.row(InlineKeyboardButton(text=truce_button_label(user), callback_data="truce_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    extra_str = f"\n⚡ Доп. атак: {user.extra_attack_count}" if user.extra_attack_count > 0 else ""
    cd_str = f"\n⏳ КД: {fmt_ttl(cd)}" if cd > 0 else ""
    nine_hint = "\n\n⚠️ <b>Последний город захвати через список городов выше — не через ботов!</b>" if cities_count >= 9 else ""

    text = (
        f"⚔️ <b>Атака — Фаза Короля</b>\n\n"
        f"{'─' * 20}\n"
        f"🏙 Городов с районами: <b>{cities_count}/10</b>\n"
        f"💪 Твоя мощь: <b>{fmt_num(user.combat_power)}</b>"
        + extra_str + cd_str +
        f"\n{'─' * 20}\n\n"
        f"Выбери город для атаки:"
        + nine_hint
    )
    return text, builder.as_markup()


@router.callback_query(F.data.startswith("king_page:"))
async def cb_king_page(cb: CallbackQuery, session: AsyncSession, user: User):
    page = int(cb.data.split(":")[1])
    text, kb = await build_king_menu(session, user, page=page)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("king_city_info:"))
async def cb_king_city_info(cb: CallbackQuery, session: AsyncSession, user: User):
    """Подробная информация о городе перед атакой — как у ботов."""
    city_id = int(cb.data.split(":")[1])

    from app.models.city import City
    from app.data.cities import KING_DISTRICT_BASE_POWER
    city_result = await session.execute(
        select(District.city_id).where(District.city_id == city_id).limit(1)
    )

    from app.repositories.city_repo import city_repo as cr
    city = await cr.get_city(session, city_id)
    if not city:
        await cb.answer("Город не найден", show_alert=True)
        return

    cd_key = cooldown_service.attack_key(user.id)
    cd = await cooldown_service.get_ttl(cd_key)
    attack_on_cd = cd > 0

    my_in_city = await session.scalar(
        select(func.count(District.id)).where(
            District.owner_id == user.id,
            District.city_id == city_id,
            District.is_captured == True,
        )
    ) or 0

    free_count = await session.scalar(
        select(func.count(District.id)).where(
            District.city_id == city_id,
            District.is_captured == False,
            District.owner_id == None,
        )
    ) or 0

    not_mine = await session.scalar(
        select(func.count(District.id)).where(
            District.city_id == city_id,
            District.is_captured == True,
            District.owner_id != user.id,
        )
    ) or 0

    city.captured_districts = min(my_in_city + not_mine, city.total_districts)

    total_initialized = await session.scalar(
        select(func.count(District.id)).where(District.city_id == city_id)
    ) or 0
    if total_initialized == 0:
        free_count = city.total_districts
    if free_count == 0 and not_mine == 0:
        await cb.answer("Все районы твои — нечего атаковать!", show_alert=True)
        return

    # Определяем противника
    dominant_id = await game_service._get_city_dominant_player(session, city_id, user.id)
    is_pvp = False
    defender_name = None
    is_fist_locked = False  # все чужие районы принадлежат Кулаку
    if dominant_id:
        defender = await user_repo.get_by_id(session, dominant_id)
        if defender and defender.phase == "king":
            is_pvp = True
            defender_name = defender.full_name
            enemy_power = int(defender.combat_power)
        elif defender and defender.phase == "fist":
            is_fist_locked = free_count == 0
            enemy_power = int(KING_DISTRICT_BASE_POWER * city.total_districts * city.district_power_multiplier)
            enemy_power = max(100, enemy_power)
        else:
            enemy_power = int(defender.combat_power * 0.7) if defender else 0
    else:
        from app.models.building import UserBuilding
        buildings_count = await session.scalar(
            select(func.count(UserBuilding.id)).where(
                UserBuilding.city_id == city_id,
                UserBuilding.is_active == True,
            )
        ) or 0
        if buildings_count > 0:
            enemy_power = int(buildings_count * 50 * city.district_power_multiplier * 0.7)
        else:
            enemy_power = int(KING_DISTRICT_BASE_POWER * city.total_districts * city.district_power_multiplier)
        enemy_power = max(100, enemy_power)

    can_win = user.combat_power >= enemy_power
    power_diff = user.combat_power - enemy_power
    power_str = f"+{fmt_num(power_diff)}" if power_diff >= 0 else fmt_num(power_diff)

    # Прогресс бар
    total = city.total_districts
    captured = min(my_in_city + not_mine, total)
    pct = min(int(captured / total * 100) if total > 0 else 0, 100)
    bar_filled = min(int(pct / 10), 10)
    progress_bar = "🟩" * bar_filled + "⬛" * (10 - bar_filled)

    size_emoji = {1: "🏘", 2: "🏙", 3: "🌆", 4: "🌇", 5: "🌃"}.get(city.type_id or 1, "🏙")

    builder = InlineKeyboardBuilder()

    if is_fist_locked:
        builder.row(InlineKeyboardButton(
            text="🔒 Все районы у Кулака — захватить нельзя",
            callback_data="noop_king"
        ))
    elif attack_on_cd:
        builder.row(InlineKeyboardButton(
            text=f"⏳ КД: {fmt_ttl(cd)}",
            callback_data="attack_cd"
        ))
    elif not can_win:
        builder.row(InlineKeyboardButton(
            text=f"❌ Недостаточно мощи (нужно {fmt_num(enemy_power)})",
            callback_data="noop_king"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="⚔️ Атаковать!",
            callback_data=f"king_attack:{city_id}"
        ))

    builder.row(InlineKeyboardButton(
        text="🔄 Обновить", callback_data=f"king_city_info:{city_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="attack"
    ))

    enemy_str = f"👤 PvP: {html.escape(defender_name)}" if is_pvp else "🤖 Бот"
    status_str = f"{'✅ Можешь победить' if can_win else '❌ Слишком слабый'} ({power_str})"

    try:
        await cb.message.edit_text(
            f"{size_emoji} <b>{html.escape(city.name)}</b>\n\n"
            f"{'─' * 20}\n"
            f"💪 Мощь противника: <b>{fmt_num(enemy_power)}</b> {enemy_str}\n"
            f"💪 Твоя мощь: <b>{fmt_num(user.combat_power)}</b>\n"
            f"📈 Разница: {power_str}\n\n"
            f"{'─' * 20}\n"
            f"🏘 Прогресс города:\n"
            f"{progress_bar} {pct}%\n"
            f"Всего районов: {captured}/{total}\n"
            f"Моих районов: <b>{my_in_city}</b>\n"
            f"Свободных: {free_count} | Чужих: {not_mine}\n\n"
            f"{'─' * 20}\n"
            f"{status_str}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("king_attack:"))
async def cb_king_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    city_id = int(cb.data.split(":")[1])

    free_count = await session.scalar(
        select(func.count(District.id)).where(
            District.city_id == city_id,
            District.is_captured == False,
            District.owner_id == None,
        )
    ) or 0
    not_mine = await session.scalar(
        select(func.count(District.id)).where(
            District.city_id == city_id,
            District.is_captured == True,
            District.owner_id != user.id,
        )
    ) or 0

    total_initialized = await session.scalar(
        select(func.count(District.id)).where(District.city_id == city_id)
    ) or 0
    if free_count == 0 and not_mine == 0 and total_initialized > 0:
        await cb.answer("Все районы твои — нечего атаковать!", show_alert=True)
        return

    lock_key = cooldown_service.attack_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("⏳ Атака уже обрабатывается", show_alert=True)
        return

    try:
        result = await game_service.king_attack(session, user, city_id)
        await session.commit()
    finally:
        await cooldown_service.release_lock(lock_key)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 {html.escape(result['message'])}",
            reply_markup=back_kb("main_menu"), parse_mode="HTML"
        )
        return

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    from app.services.quest_service import quest_service
    await quest_service.add_progress(session, user, "attacks")
    if result["win"]:
        await quest_service.add_progress(session, user, "wins")

    # После победы — остаёмся в том же городе
    if result["win"]:
        crit_str = "⚡КРИТ! " if result.get("is_crit") else ""
        is_pvp = result.get("defender_name") is not None
        if is_pvp:
            taken = result.get("districts_taken", 0)
            await cb.answer(
                f"✅ {crit_str}Победа PvP! +{taken} районов у {result['defender_name']}",
                show_alert=False,
            )
        else:
            gained = result.get("districts_gained", 0)
            await cb.answer(
                f"✅ {crit_str}Победа! +{gained} районов в {result['city']}",
                show_alert=False,
            )
        await cb_king_city_info(cb, session, user)
        return

    # При поражении — показываем результат с кнопками
    is_pvp = result.get("defender_name") is not None
    city_total = result.get('city_total', 0)
    city_captured = result.get('city_captured', 0)
    progress_str = ""
    if city_total > 0:
        pct = min(int(city_captured / city_total * 100), 100)
        bar_filled = min(int(pct / 10), 10)
        progress_bar = "🟩" * bar_filled + "⬛" * (10 - bar_filled)
        progress_str = f"\n{progress_bar} {pct}%\n"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="⚔️ Атаковать снова", callback_data=f"king_city_info:{city_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ К городам", callback_data="attack"
    ))

    if is_pvp:
        text = (
            f"❌ <b>Поражение в PvP!</b>\n\n"
            f"{'─' * 20}\n"
            f"Противник: <b>{html.escape(result['defender_name'])}</b>\n"
            f"Город: <b>{html.escape(result['city'])}</b>\n"
            + progress_str +
            f"{'─' * 20}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}"
        )
    else:
        text = (
            f"❌ <b>Поражение!</b>\n\n"
            f"{'─' * 20}\n"
            f"Город: <b>{html.escape(result['city'])}</b>\n"
            + progress_str +
            f"Районов в городе: {city_captured}/{city_total}\n\n"
            f"{'─' * 20}\n"
            f"💪 Твоя мощь: {fmt_num(result['user_power'])}\n"
            f"🤖 Мощь противника: {fmt_num(result['bot_power'])}"
        )

    try:
        await cb.message.edit_text(
            text, reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data == "noop_king")
async def cb_noop_king(cb: CallbackQuery):
    await cb.answer()