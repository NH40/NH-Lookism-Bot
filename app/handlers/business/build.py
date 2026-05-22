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
from app.data.buildings import BUILDINGS_BY_ID, BUILDINGS_BY_PATH
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

    buildings = BUILDINGS_BY_PATH.get(user.business_path, [])
    used = await building_repo.get_used_districts(session, user.id)
    total = await city_repo.get_total_districts(session, user.id)
    free = max(0, total - used)

    builder = InlineKeyboardBuilder()
    for b in buildings:
        discount = user.building_discount_percent
        cost = max(1, int(b.district_cost * (1 - discount / 100)))
        can = "✅" if free >= cost else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can} {b.emoji} {b.name} | "
                 f"💰 {fmt_num(b.base_income)}/мин | 🏘 {cost}р.",
            callback_data=f"biz_select_building:{b.id}"
        ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="business"
    ))

    path_info = PATH_INFO.get(user.business_path, {})
    try:
        await cb.message.edit_text(
            f"🏗 <b>Строительство</b>\n\n"
            f"Путь: {path_info.get('emoji','')} {path_info.get('name','')}\n"
            f"🏘 Свободно районов: {free}/{total}\n\n"
            f"Выбери здание:",
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

    buildings = BUILDINGS_BY_PATH.get(user.business_path, [])

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
            text=f"{can} {b.emoji} {b.name} | "
                 f"💰 {fmt_num(b.base_income)}/мин | 🏘 {cost}р.",
            callback_data=f"biz_build_in:{b.id}:{city_id}"
        ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data=f"biz_city:{city_id}"
    ))

    city = await city_repo.get_city(session, city_id)
    city_name = city.name if city else f"Город {city_id}"
    try:
        await cb.message.edit_text(
            f"🏗 <b>Строительство в {city_name}</b>\n\n"
            f"🏘 Свободно районов: {free}/{districts_in_city}\n\n"
            f"Выбери здание:",
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

    builder = InlineKeyboardBuilder()
    available_cities = []
    for city_id, city_name in cities_with_districts:
        districts_count = await session.scalar(
            select(func.count(District.id)).where(
                District.owner_id == user.id,
                District.city_id == city_id,
                District.is_captured == True,
            )
        ) or 0
        used = await building_repo.get_used_districts_in_city(
            session, user.id, city_id
        )
        free_in_city = districts_count - used
        if free_in_city >= cost:
            available_cities.append((city_id, city_name, free_in_city))
            builder.row(InlineKeyboardButton(
                text=f"✅ 🏙 {city_name} | 🏘 свободно: {free_in_city}",
                callback_data=f"biz_build_in:{building_id}:{city_id}"
            ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="biz_build"
    ))

    if not available_cities:
        no_cities_text = (
            f"🏗 <b>{cfg.emoji} {cfg.name}</b>\n\n"
            f"💰 Доход: {fmt_num(cfg.base_income)}/мин\n"
            f"🏘 Стоимость: {cost} районов\n\n"
            f"❌ Нет городов с достаточным количеством свободных районов.\n"
            f"<i>Захвати больше районов или снеси другие здания.</i>"
        )
        try:
            await cb.message.edit_text(no_cities_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            pass
        return

    try:
        await cb.message.edit_text(
            f"🏗 <b>{cfg.emoji} {cfg.name}</b>\n\n"
            f"💰 Доход: {fmt_num(cfg.base_income)}/мин\n"
            f"🏘 Стоимость: {cost} районов\n\n"
            f"Выбери город для строительства:",
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
