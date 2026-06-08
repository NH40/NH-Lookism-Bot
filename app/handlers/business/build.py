from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.city import District, City
from app.services.business_service import business_service
from app.repositories.building_repo import building_repo
from app.repositories.city_repo import city_repo
from app.utils.formatters import fmt_num
from app.data.buildings import BUILDINGS_BY_ID, BUILDINGS_BY_PATH, BUILDINGS
from ._common import PATH_INFO, _show_business_main
from .buildings import _show_city_buildings

router = Router()


@router.callback_query(F.data == "biz_build")
async def cb_biz_build(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    if not user.business_path:
        await cb.answer("Сначала выберите путь", show_alert=True)
        return

    biz_genius = getattr(user, "business_genius_level", 0)
    all_path_buildings = BUILDINGS_BY_PATH.get(user.business_path, [])
    available_buildings = [b for b in all_path_buildings if b.min_biz_genius <= biz_genius]
    locked_buildings = [b for b in all_path_buildings if b.min_biz_genius > biz_genius]

    used = await building_repo.get_used_districts(session, user.id)
    total = await city_repo.get_total_districts(session, user.id)
    free = max(0, total - used)

    builder = InlineKeyboardBuilder()
    for b in available_buildings:
        discount = user.building_discount_percent
        cost = max(1, int(b.district_cost * (1 - discount / 100)))
        can = "✅" if free >= cost else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can} {b.emoji} {b.name}  ·  {fmt_num(b.base_income)}/мин  ·  {cost} р.",
            callback_data=f"biz_select_building:{b.id}"
        ))

    if locked_buildings:
        next_locked_genius = min(b.min_biz_genius for b in locked_buildings)
        for b in locked_buildings:
            if b.min_biz_genius == next_locked_genius:
                builder.row(InlineKeyboardButton(
                    text=f"🔒 {b.emoji} {b.name}  ·  Гений Ур.{b.min_biz_genius}",
                    callback_data="noop_biz"
                ))

    builder.row(InlineKeyboardButton(text="⚡ Авто-застройка", callback_data="biz_auto_build"))
    builder.row(InlineKeyboardButton(text="🎖 Гений бизнеса", callback_data="biz_genius_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="business"))

    path_info = PATH_INFO.get(user.business_path, {})
    from app.constants.raid import BIZ_GENIUS_INCOME_BONUS
    genius_bonus = BIZ_GENIUS_INCOME_BONUS[biz_genius - 1] if biz_genius > 0 else 0

    genius_str = f"Ур.{biz_genius}/5" + (f"  (+{genius_bonus}% к доходу)" if genius_bonus else "")

    try:
        await cb.message.edit_text(
            f"🏗 <b>Строительство</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📍 {path_info.get('emoji','')} {path_info.get('name','')}\n"
            f"🏘 Свободных районов: <b>{free}</b> из {total}\n"
            f"🎖 Гений бизнеса: <b>{genius_str}</b>\n\n"
            f"Выберите здание для постройки:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("biz_build_city:"))
async def cb_biz_build_city(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    city_id = int(cb.data.split(":")[1])
    if not user.business_path:
        await cb.answer("Сначала выберите путь", show_alert=True)
        return

    biz_genius = getattr(user, "business_genius_level", 0)
    all_path_buildings = BUILDINGS_BY_PATH.get(user.business_path, [])
    buildings = [b for b in all_path_buildings if b.min_biz_genius <= biz_genius]

    districts_in_city = await session.scalar(
        select(func.count(District.id)).where(
            District.owner_id == user.id,
            District.city_id == city_id,
            District.is_captured == True,
        )
    ) or 0

    used_in_city = await building_repo.get_used_districts_in_city(
        session, user.id, city_id
    )
    free = max(0, districts_in_city - used_in_city)

    builder = InlineKeyboardBuilder()
    for b in buildings:
        discount = user.building_discount_percent
        cost = max(1, int(b.district_cost * (1 - discount / 100)))
        can = "✅" if free >= cost else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can} {b.emoji} {b.name}  ·  {fmt_num(b.base_income)}/мин  ·  {cost} р.",
            callback_data=f"biz_build_in:{b.id}:{city_id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"biz_city:{city_id}"))

    city = await city_repo.get_city(session, city_id)
    city_name = city.name if city else f"Город {city_id}"
    try:
        await cb.message.edit_text(
            f"🏗 <b>Строительство — {city_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏘 Свободных районов: <b>{free}</b> из {districts_in_city}\n\n"
            f"Выберите здание для постройки:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("biz_select_building:"))
async def cb_biz_select_building(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    building_id = cb.data.split(":")[1]
    cfg = BUILDINGS_BY_ID.get(building_id)
    if not cfg:
        await cb.answer("Здание не найдено", show_alert=True)
        return

    result = await session.execute(
        select(City.id, City.name).distinct()
        .join(District, District.city_id == City.id)
        .where(
            District.owner_id == user.id,
            District.is_captured == True,
        )
    )
    cities_with_districts = result.all()

    if not cities_with_districts:
        await cb.answer("Нет районов для строительства", show_alert=True)
        return

    discount = user.building_discount_percent
    cost = max(1, int(cfg.district_cost * (1 - discount / 100)))

    used_per_city = await building_repo.get_used_districts_per_city(session, user.id)

    dist_rows = (await session.execute(
        select(District.city_id, func.count(District.id).label("cnt"))
        .where(
            District.owner_id == user.id,
            District.city_id.in_([c[0] for c in cities_with_districts]),
            District.is_captured == True,
        )
        .group_by(District.city_id)
    )).all()
    dist_per_city = {city_id: cnt for city_id, cnt in dist_rows}

    builder = InlineKeyboardBuilder()
    available_cities = []
    for city_id, city_name in cities_with_districts:
        districts_count = dist_per_city.get(city_id, 0)
        free_in_city = districts_count - used_per_city.get(city_id, 0)
        if free_in_city >= cost:
            available_cities.append((city_id, city_name, free_in_city))
            builder.row(InlineKeyboardButton(
                text=f"✅ 🏙 {city_name}  ·  свободно: {free_in_city} р.",
                callback_data=f"biz_build_in:{building_id}:{city_id}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="biz_build"))

    if not available_cities:
        try:
            await cb.message.edit_text(
                f"{cfg.emoji} <b>{cfg.name}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 Доход: {fmt_num(cfg.base_income)}/мин\n"
                f"🏘 Стоимость: {cost} районов\n\n"
                f"❌ <b>Нет городов с достаточным количеством свободных районов.</b>\n"
                f"<i>Захвати больше районов или снеси существующие здания.</i>",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    try:
        await cb.message.edit_text(
            f"{cfg.emoji} <b>{cfg.name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Доход: {fmt_num(cfg.base_income)}/мин\n"
            f"🏘 Стоимость: {cost} районов\n\n"
            f"Выберите город для строительства:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("biz_build_in:"))
async def cb_biz_build_in(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.biz_build_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("Подожди...", show_alert=False)
        return

    parts = cb.data.split(":")
    building_id = parts[1]
    city_id = int(parts[2])

    result = await business_service.buy_building(
        session, user, building_id, city_id
    )
    if result["ok"]:
        cfg = BUILDINGS_BY_ID.get(building_id)
        name = cfg.name if cfg else building_id
        emoji = cfg.emoji if cfg else "🏢"
        await cb.answer(f"✅ {emoji} {name} построено!")
        await _show_business_main(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data == "biz_auto_build")
async def cb_biz_auto_build(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    if not user.business_path:
        await cb.answer("Сначала выберите путь", show_alert=True)
        return

    biz_genius = getattr(user, "business_genius_level", 0)
    available_buildings = [
        b for b in BUILDINGS_BY_PATH.get(user.business_path, [])
        if b.min_biz_genius <= biz_genius
    ]

    result = await session.execute(
        select(District.city_id, func.count(District.id).label("cnt"))
        .where(
            District.owner_id == user.id,
            District.is_captured == True,
            District.city_id.isnot(None),
        )
        .group_by(District.city_id)
    )
    city_rows = result.all()

    used_per_city = await building_repo.get_used_districts_per_city(session, user.id)
    free_per_city: dict[int, int] = {
        city_id: max(0, dist_count - used_per_city.get(city_id, 0))
        for city_id, dist_count in city_rows
    }

    total_free = sum(free_per_city.values())

    builder = InlineKeyboardBuilder()
    has_any = False
    for b in available_buildings:
        discount = user.building_discount_percent
        cost = max(2, int(b.district_cost * (1 - discount / 100)))
        if cost % 2 != 0:
            cost += 1
        max_count = sum(f // cost for f in free_per_city.values())
        if max_count > 0:
            has_any = True
            builder.row(InlineKeyboardButton(
                text=f"⚡ {b.emoji} {b.name} ×{max_count}  (+{fmt_num(b.base_income * max_count)}/мин)",
                callback_data=f"biz_auto_exec:{b.id}"
            ))

    if not has_any:
        builder.row(InlineKeyboardButton(text="❌ Нет свободных районов", callback_data="noop_biz"))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="biz_build"))

    try:
        await cb.message.edit_text(
            f"⚡ <b>Авто-застройка</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏘 Свободных районов: <b>{total_free}</b> (суммарно по всем городам)\n\n"
            f"Выберите здание — оно будет построено максимальное количество раз во всех городах:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("biz_auto_exec:"))
async def cb_biz_auto_exec(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.biz_build_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=30):
        await cb.answer("Подожди...", show_alert=False)
        return

    building_id = cb.data.split(":")[1]
    result = await business_service.buy_building_max(session, user, building_id)

    if result["ok"]:
        n = result["count"]
        cfg = BUILDINGS_BY_ID.get(building_id)
        name = cfg.name if cfg else building_id
        emoji = cfg.emoji if cfg else "🏢"
        if n > 0:
            await cb.answer(f"✅ Построено: {emoji} {name} ×{n}!", show_alert=True)
        else:
            await cb.answer("Нет свободных районов для постройки", show_alert=True)
        await _show_business_main(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data == "noop_biz")
async def cb_noop_biz(cb: CallbackQuery):
    await cb.answer("🔒 Требуется Гений бизнеса", show_alert=False)
