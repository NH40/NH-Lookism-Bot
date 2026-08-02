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
from app.utils.formatters import fmt_num, fmt_ttl, clamp_enemy_power
from app.utils.truce import truce_button_label
from app.utils.menu_media import send_menu
import html

router = Router()


async def build_king_menu(session, user, page: int = 0):
    cd_key = cooldown_service.attack_key(user.id)
    cd = await cooldown_service.get_ttl(cd_key)

    from app.data.cities import DEFAULT_COUNTRY
    cities = await city_repo.get_available_king_cities(session, user.country or DEFAULT_COUNTRY)

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
            my_count_all = (row.my_count if row else 0) or 0
            # Все районы уже мои, но трон (City.owner_id) ещё не мой — трон
            # "завис" (владелец мог стать Императором/сменить страну уже
            # ПОСЛЕ того, как я стал 100%-владельцем районов, и с тех пор
            # нечего было захватывать, чтобы перепроверка сработала заново).
            # Не прячем такой город из списка — иначе трон не забрать никогда
            # (см. king_attack: там есть отдельная ветка "дожим трона").
            throne_unclaimed = my_count_all >= city.total_districts and city.owner_id != user.id
            if row and (row.free_count or 0) == 0 and (row.not_mine or 0) == 0 and not throne_unclaimed:
                continue

            dominant_id = dominant_by_city.get(cid)
            defender = defenders.get(dominant_id) if dominant_id else None

            # Пропускаем города, где все чужие районы принадлежат Кулаку и свободных нет
            if (
                defender and getattr(defender, 'phase', None) == "fist"
                and (row.free_count or 0) == 0
            ):
                continue

            if throne_unclaimed:
                def_str = "👑 забрать трон"
            elif defender and defender.phase == "king":
                def_power = clamp_enemy_power(int(defender.combat_power or 0), user.combat_power)
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
    ruled_count = await game_service._count_ruled_cities(session, user.id)
    builder.row(InlineKeyboardButton(text="👑 Борьба за трон", callback_data="king_challenge_list"))

    emperor_challenge_str = ""
    if await game_service._is_emperor_eligible(session, user):
        from app.data.cities import DEFAULT_COUNTRY as _DC
        _country = user.country or _DC
        _emperors_count = await session.scalar(
            select(func.count(User.id)).where(User.phase == "emperor", User.country == _country)
        ) or 0
        if _emperors_count > 0:
            builder.row(InlineKeyboardButton(
                text="⚔️ Бросить вызов Императору",
                callback_data="emperor_challenge_list",
            ))
            emperor_challenge_str = (
                "\n\n🏆 Вы захватили всю страну! Доступен вызов Императору — "
                "победите его и займите трон."
            )

    builder.row(InlineKeyboardButton(text=truce_button_label(user), callback_data="truce_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    extra_str = f"\n⚡ Доп. атак: {user.extra_attack_count}" if user.extra_attack_count > 0 else ""
    cd_str = f"\n⏳ КД: {fmt_ttl(cd)}" if cd > 0 else ""

    text = (
        f"⚔️ <b>Атака — Фаза Короля</b>\n\n"
        f"{'─' * 20}\n"
        f"🏙 Городов с районами: <b>{cities_count}</b>\n"
        f"👑 Городов на троне: <b>{ruled_count}</b>\n"
        f"🤝 Вассалов: <b>{user.vassal_count}</b>"
        + (f" | 🫡 Плачу дань королю" if user.suzerain_id else "") +
        f"\n💪 Твоя мощь: <b>{fmt_num(user.combat_power)}</b>"
        + extra_str + cd_str + emperor_challenge_str +
        f"\n{'─' * 20}\n\n"
        f"Выбери город для атаки:"
    )
    from app.data.cities import COUNTRY_BY_CODE, DEFAULT_COUNTRY
    photo = COUNTRY_BY_CODE[user.country or DEFAULT_COUNTRY].image
    return text, builder.as_markup(), photo


@router.callback_query(F.data.startswith("king_page:"))
async def cb_king_page(cb: CallbackQuery, session: AsyncSession, user: User):
    page = int(cb.data.split(":")[1])
    text, kb, photo = await build_king_menu(session, user, page=page)
    from app.utils.menu_media import send_menu
    await send_menu(cb, text, kb, photo)
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
    throne_unclaimed = free_count == 0 and not_mine == 0 and city.owner_id != user.id
    if free_count == 0 and not_mine == 0 and not throne_unclaimed:
        await cb.answer("Все районы твои — нечего атаковать!", show_alert=True)
        return

    if throne_unclaimed:
        # Все районы уже мои, но трон завис за прежним владельцем (стал
        # Императором/сменил страну — это нормально для налога, но САМ
        # трон должен перейти новому 100%-владельцу районов). Нет боя за
        # районы — только "дожим" трона (см. king_attack).
        builder = InlineKeyboardBuilder()
        cd_key_throne = cooldown_service.attack_key(user.id)
        cd_throne = await cooldown_service.get_ttl(cd_key_throne)
        if cd_throne > 0:
            builder.row(InlineKeyboardButton(text=f"⏳ КД: {fmt_ttl(cd_throne)}", callback_data="attack_cd"))
        else:
            builder.row(InlineKeyboardButton(text="👑 Забрать трон", callback_data=f"king_attack:{city_id}"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="attack"))

        size_emoji = {1: "🏘", 2: "🏙", 3: "🌆", 4: "🌇", 5: "🌃"}.get(city.type_id or 1, "🏙")
        await send_menu(
            cb,
            f"{size_emoji} <b>{html.escape(city.name)}</b>\n\n"
            f"{'─' * 20}\n"
            f"Ты владеешь всеми районами города, но трон ещё не перешёл к тебе.\n\n"
            f"{'─' * 20}",
            builder.as_markup(),
        )
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
            enemy_power = clamp_enemy_power(int(defender.combat_power), user.combat_power)
        elif defender and defender.phase == "fist":
            is_fist_locked = free_count == 0
            enemy_power = int(KING_DISTRICT_BASE_POWER * city.total_districts * city.district_power_multiplier)
            enemy_power = clamp_enemy_power(max(100, enemy_power), user.combat_power)
        else:
            enemy_power = clamp_enemy_power(int(defender.combat_power * 0.7), user.combat_power) if defender else 0
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
        enemy_power = clamp_enemy_power(max(100, enemy_power), user.combat_power)

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

    await send_menu(
        cb,
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
        builder.as_markup(),
    )


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
        # Все районы мои — но если трон города (City.owner_id) ещё не мой,
        # пропускаем дальше в king_attack: там есть отдельная ветка "дожим
        # трона" (см. king.py service) для случая, когда трон завис за
        # владельцем, который давно не защищается (стал Императором/сменил
        # страну — это нормально, налог должен идти ему, но САМ трон должен
        # переходить новому 100%-владельцу районов).
        city = await city_repo.get_city(session, city_id)
        if not city or city.owner_id == user.id:
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
        await send_menu(cb, f"🎉 {html.escape(result['message'])}", back_kb("main_menu"))
        return

    if result.get("title_lost"):
        await send_menu(cb, f"💀 <b>{html.escape(result['message'])}</b>", back_kb("attack"))
        return

    if result.get("throne_claimed"):
        await send_menu(cb, f"👑 {html.escape(result['message'])}", back_kb("attack"))
        return

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    if getattr(user, "fame_set_gaprena", False):
        from app.services.fame_service import fame_service
        await fame_service.gain_overcome_stack(user.id)

    from app.services.quest_service import quest_service
    await quest_service.add_progress(session, user, "attacks")
    if result["win"]:
        await quest_service.add_progress(session, user, "wins")
        from app.utils.region_activity import record
        await record(session, user.id, "attack_king")

    # После победы — остаёмся в том же городе
    if result["win"]:
        crit_str = "⚡КРИТ! " if result.get("is_crit") else ""
        is_pvp = result.get("defender_name") is not None
        if is_pvp:
            taken = result.get("districts_taken", 0)
            cas = result.get("casualties") or {}
            cas_str = (
                f" | ты: −{cas['attacker_statists_lost']}стат/−{cas['attacker_cards_lost']}карт, "
                f"он: −{cas['defender_statists_lost']}стат/−{cas['defender_cards_lost']}карт"
                if any(cas.get(k) for k in (
                    "attacker_statists_lost", "attacker_cards_lost",
                    "defender_statists_lost", "defender_cards_lost",
                )) else ""
            )
            await cb.answer(
                f"✅ {crit_str}Победа PvP! +{taken} районов у {result['defender_name']}{cas_str}",
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
        cas = result.get("casualties") or {}
        cas_str = (
            f"\n💀 Твои потери в бою: −{cas['attacker_statists_lost']} статистов, "
            f"−{cas['attacker_cards_lost']} карточек"
            if cas.get("attacker_statists_lost") or cas.get("attacker_cards_lost") else ""
        )
        text = (
            f"❌ <b>Поражение в PvP!</b>\n\n"
            f"{'─' * 20}\n"
            f"Противник: <b>{html.escape(result['defender_name'])}</b>\n"
            f"Город: <b>{html.escape(result['city'])}</b>\n"
            + progress_str +
            f"{'─' * 20}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}"
            + cas_str
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

    await send_menu(cb, text, builder.as_markup())


@router.callback_query(F.data == "noop_king")
async def cb_noop_king(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data == "king_challenge_list")
async def cb_king_challenge_list(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.data.cities import DEFAULT_COUNTRY
    from app.utils.truce import is_truce_active

    country = user.country or DEFAULT_COUNTRY
    rivals_r = await session.execute(
        select(User).where(
            User.phase == "king",
            User.country == country,
            User.id != user.id,
        ).order_by(User.combat_power.desc()).limit(10)
    )
    rivals = rivals_r.scalars().all()

    if not rivals:
        await cb.answer("В твоей стране больше нет других королей", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for r in rivals:
        power = clamp_enemy_power(int(r.combat_power), user.combat_power)
        if is_truce_active(r):
            builder.row(InlineKeyboardButton(
                text=f"🕊 {r.full_name} | 💪 {fmt_num(power)} (перемирие)",
                callback_data="noop_king"
            ))
        else:
            builder.row(InlineKeyboardButton(
                text=f"⚔️ {r.full_name} | 💪 {fmt_num(power)}",
                callback_data=f"king_challenge_attack:{r.id}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="attack"))

    await send_menu(
        cb,
        "👑 <b>Борьба за трон</b>\n\n"
        "Победишь — соперник станет твоим вассалом (платит 20% дохода).\n"
        "Проиграешь — станешь вассалом сам.\n"
        "Вызов раз в час, только внутри своей страны.\n\n"
        f"💪 Твоя мощь: {fmt_num(user.combat_power)}",
        builder.as_markup(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("king_challenge_attack:"))
async def cb_king_challenge_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    defender_id = int(cb.data.split(":")[1])

    lock_key = cooldown_service.king_challenge_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("⏳ Вызов уже обрабатывается", show_alert=True)
        return

    try:
        result = await game_service.king_challenge_throne(session, user, defender_id)
        await session.commit()
    finally:
        await cooldown_service.release_lock(lock_key)

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
    if result["win"]:
        text = (
            f"✅ <b>Победа!{crit_str}</b>\n\n"
            f"Противник: {html.escape(result['defender_name'])}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}\n\n"
            f"👑 {html.escape(result['defender_name'])} стал твоим вассалом! +20% от его дохода."
        )
    else:
        text = (
            f"❌ <b>Поражение!</b>\n\n"
            f"Противник: {html.escape(result['defender_name'])}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}\n\n"
            f"🫡 Ты стал вассалом {html.escape(result['defender_name'])} — платишь ему 20% дохода."
        )
    await send_menu(cb, text, back_kb("attack"))


# ── Вызов Императора страны (Король, захвативший всю страну) ─────────────────

@router.callback_query(F.data == "emperor_challenge_list")
async def cb_emperor_challenge_list(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.phase != "king":
        await cb.answer("Только для фазы Короля", show_alert=True)
        return
    if not await game_service._is_emperor_eligible(session, user):
        await cb.answer("Сначала захватите все города своей страны (сами + вассалы)", show_alert=True)
        return

    from app.data.cities import DEFAULT_COUNTRY
    from app.utils.truce import is_truce_active
    country = user.country or DEFAULT_COUNTRY
    emperors_r = await session.execute(
        select(User).where(User.phase == "emperor", User.country == country)
    )
    emperors = emperors_r.scalars().all()
    if not emperors:
        await cb.answer("В твоей стране больше нет Императора", show_alert=True)
        return

    from app.config.game_balance import EMPEROR_CHALLENGE_ROUNDS_TO_WIN
    builder = InlineKeyboardBuilder()
    for e in emperors:
        power = clamp_enemy_power(int(e.combat_power), user.combat_power)
        progress_key = cooldown_service.emperor_challenge_progress_key(user.id, e.id)
        wins = int(await cooldown_service.redis.get(progress_key) or 0)
        round_str = f" [{wins}/{EMPEROR_CHALLENGE_ROUNDS_TO_WIN}]" if wins else ""
        if is_truce_active(e):
            builder.row(InlineKeyboardButton(
                text=f"🕊 {e.full_name} | 💪 {fmt_num(power)} (перемирие)",
                callback_data="noop_king"
            ))
        else:
            builder.row(InlineKeyboardButton(
                text=f"⚔️ {e.full_name} | 💪 {fmt_num(power)}{round_str}",
                callback_data=f"emperor_challenge_attack:{e.id}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="attack"))

    await send_menu(
        cb,
        "🏆 <b>Вызов Императору страны</b>\n\n"
        f"Нужно победить {EMPEROR_CHALLENGE_ROUNDS_TO_WIN} раза ПОДРЯД (раз в час за попытку) — "
        f"поражение сбрасывает счёт побед в 0, придётся начинать серию заново.\n"
        f"На решающей победе — займёшь трон и станешь Императором, а он потеряет "
        f"все города и вернётся на этап Банды (прокачка не теряется).\n"
        "Вызов только внутри своей страны.\n\n"
        f"💪 Твоя мощь: {fmt_num(user.combat_power)}",
        builder.as_markup(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("emperor_challenge_attack:"))
async def cb_emperor_challenge_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    emperor_id = int(cb.data.split(":")[1])

    lock_key = cooldown_service.emperor_challenge_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("⏳ Вызов уже обрабатывается", show_alert=True)
        return

    try:
        result = await game_service.challenge_emperor(session, user, emperor_id)
        await session.commit()
    finally:
        await cooldown_service.release_lock(lock_key)

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    if result.get("promoted"):
        await send_menu(cb, f"🎉 {html.escape(result['message'])}", back_kb("main_menu"))
        return

    crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
    if result["win"]:
        text = (
            f"✅ <b>Победа в раунде!{crit_str}</b>\n\n"
            f"Противник: {html.escape(result['defender_name'])}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}\n\n"
            f"Счёт побед: {result['rounds_won']}/{result['rounds_needed']} — "
            f"побеждай подряд, поражение сбросит счёт."
        )
    else:
        text = (
            f"❌ <b>Поражение!</b>\n\n"
            f"Противник: {html.escape(result['defender_name'])}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}\n\n"
            f"Счёт побед сброшен в 0 — трон остался за прежним Императором."
        )
    await send_menu(cb, text, back_kb("attack"))