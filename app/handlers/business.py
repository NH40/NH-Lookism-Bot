from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.building import UserBuilding
from app.services.business_service import business_service
from app.repositories.building_repo import building_repo
from app.repositories.city_repo import city_repo
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num
from app.data.buildings import BUILDINGS_BY_ID, BUILDINGS_BY_PATH

router = Router()


PATH_INFO = {
    "legal": {
        "name": "Легальный",
        "emoji": "⚖️",
        "desc": "Стабильный путь. Не влияет на влияние.",
    },
    "illegal": {
        "name": "Нелегальный",
        "emoji": "🕶",
        "desc": "Забирает влияние за постройку, но даёт больше прибыли.",
    },
    "political": {
        "name": "Политика",
        "emoji": "🏛",
        "desc": "Меньше зданий, но повышает влияние.",
    },
}


@router.callback_query(F.data == "business")
async def cb_business(cb: CallbackQuery, session: AsyncSession, user: User):
    if not user.business_path:
        # Выбор пути
        builder = InlineKeyboardBuilder()
        for path_id, info in PATH_INFO.items():
            builder.button(
                text=f"{info['emoji']} {info['name']}",
                callback_data=f"biz_path:{path_id}"
            )
        builder.adjust(1)
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))

        await cb.message.edit_text(
            "🏢 <b>Бизнес — Выбор пути</b>\n\n"
            "⚖️ <b>Легальный</b>\nСтабильный доход, не влияет ни на что\n\n"
            "🕶 <b>Нелегальный</b>\nЗабирает влияние за постройку, но даёт больше прибыли\n\n"
            "🏛 <b>Политика</b>\nМеньше доступных зданий, но повышает влияние\n\n"
            "<i>Выбор нельзя изменить до гибели или пробуждения!</i>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
        return

    # Список зданий игрока с группировкой по городам
    info = await business_service.get_income_breakdown(session, user)
    path_info = PATH_INFO.get(user.business_path, {})

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🏗 Построить здание", callback_data="biz_build"
    ))
    builder.row(InlineKeyboardButton(
        text="🏢 Мои здания", callback_data="biz_my_buildings"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))

    bonuses = []
    if info['total_bonus_percent']:
        bonuses.append(f"  📈 Бонусы: +{info['total_bonus_percent']}%")
    if info['potion_bonus']:
        bonuses.append(f"  🧪 Зелье: +{info['potion_bonus']}%")

    bonus_str = "\n" + "\n".join(bonuses) if bonuses else ""

    await cb.message.edit_text(
        f"🏢 <b>Бизнес</b>\n\n"
        f"📍 Путь: {path_info.get('emoji','')} {path_info.get('name','')}\n"
        f"{'─'*20}\n"
        f"💰 Базовый доход: {fmt_num(info['base_income'])} NHCoin/мин\n"
        f"📈 Итого с бонусами: {fmt_num(info['final_income'])} NHCoin/мин"
        + bonus_str,
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("biz_path:"))
async def cb_biz_path(cb: CallbackQuery, session: AsyncSession, user: User):
    path = cb.data.split(":")[1]
    if user.business_path:
        await cb.answer("Путь уже выбран", show_alert=True)
        return
    user.business_path = path
    await session.flush()
    path_info = PATH_INFO.get(path, {})
    await cb.answer(f"✅ Путь {path_info.get('name','')} выбран!")
    await cb_business(cb, session, user)


@router.callback_query(F.data == "biz_my_buildings")
async def cb_biz_my_buildings(cb: CallbackQuery, session: AsyncSession, user: User):
    """Показывает здания игрока сгруппированные по городам."""
    buildings = await building_repo.get_user_buildings(session, user.id)

    if not buildings:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="🏗 Построить первое здание", callback_data="biz_build"
        ))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="business"))
        await cb.message.edit_text(
            "🏢 <b>Мои здания</b>\n\nЗданий нет",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
        return

    info = await business_service.get_income_breakdown(session, user)

    lines = [
        f"🏢 <b>Мои здания</b>\n\n"
        f"💰 Базовый доход: {fmt_num(info['base_income'])} NHCoin/мин\n"
        f"📈 Итого с бонусами: {fmt_num(info['final_income'])} NHCoin/мин\n\n"
        f"Выбери город чтобы управлять зданиями:"
    ]

    # Группируем по city_name (через district)
    city_buildings: dict[int, list] = {}
    for b in buildings:
        city_buildings.setdefault(b.city_id or 0, []).append(b)

    builder = InlineKeyboardBuilder()
    for city_id, city_blds in city_buildings.items():
        if city_id:
            city = await city_repo.get_city(session, city_id)
            city_name = city.name if city else f"Город {city_id}"
            type_str = f"{city.type_id} тип." if city else ""
        else:
            city_name = "Без города"
            type_str = ""
        builder.button(
            text=f"🏙 {city_name} ({type_str})",
            callback_data=f"biz_city:{city_id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="🏗 Построить ещё", callback_data="biz_build"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="business"))

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("biz_city:"))
async def cb_biz_city(cb: CallbackQuery, session: AsyncSession, user: User):
    """Показывает здания в конкретном городе с возможностью сноса."""
    city_id = int(cb.data.split(":")[1])

    buildings = await session.execute(
        select(UserBuilding).where(
            UserBuilding.user_id == user.id,
            UserBuilding.city_id == city_id if city_id else UserBuilding.city_id.is_(None),
            UserBuilding.is_active == True,
        )
    )
    buildings = buildings.scalars().all()

    if city_id:
        city = await city_repo.get_city(session, city_id)
        city_name = city.name if city else f"Город {city_id}"
    else:
        city_name = "Без города"

    lines = [f"🏙 <b>{city_name}</b>\n\nПостройки:\n"]
    for b in buildings:
        cfg = BUILDINGS_BY_ID.get(b.building_type)
        name = cfg.name if cfg else b.building_type
        emoji = cfg.emoji if cfg else "🏢"
        income = b.base_income * b.count
        lines.append(
            f"  {emoji} {name} ×{b.count}\n"
            f"  💰 {income}/мин (база) | 🏘 {b.district_cost} р."
        )

    lines.append("\n<i>Нажми на здание чтобы снести 1 штуку</i>")

    builder = InlineKeyboardBuilder()
    for b in buildings:
        cfg = BUILDINGS_BY_ID.get(b.building_type)
        name = cfg.name if cfg else b.building_type
        emoji = cfg.emoji if cfg else "🏢"
        builder.button(
            text=f"🔨 {emoji} {name} ×{b.count} | 💰 {b.base_income * b.count}/мин",
            callback_data=f"biz_demolish:{b.id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="biz_my_buildings"
    ))

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("biz_demolish:"))
async def cb_biz_demolish(cb: CallbackQuery, session: AsyncSession, user: User):
    building_id = int(cb.data.split(":")[1])
    result = await session.execute(
        select(UserBuilding).where(
            UserBuilding.id == building_id,
            UserBuilding.user_id == user.id,
        )
    )
    building = result.scalar_one_or_none()
    if not building:
        await cb.answer("Здание не найдено", show_alert=True)
        return

    city_id = building.city_id

    if building.count > 1:
        building.count -= 1
        # Возвращаем часть районов
        cost_per = building.district_cost // (building.count + 1)
        building.district_cost -= cost_per
    else:
        building.is_active = False

    await session.flush()
    await business_service._recalc_income(session, user)

    await cb.answer("🔨 Здание снесено!")
    # Возвращаемся к городу
    cb.data = f"biz_city:{city_id or 0}"
    await cb_biz_city(cb, session, user)


@router.callback_query(F.data == "biz_build")
async def cb_biz_build(cb: CallbackQuery, session: AsyncSession, user: User):
    if not user.business_path:
        await cb.answer("Сначала выберите путь", show_alert=True)
        return

    buildings = BUILDINGS_BY_PATH.get(user.business_path, [])
    used = await building_repo.get_used_districts(session, user.id)
    total = await city_repo.get_total_districts(session, user.id)
    free = total - used

    builder = InlineKeyboardBuilder()
    for b in buildings:
        discount = user.building_discount_percent
        cost = max(1, int(b.district_cost * (1 - discount / 100)))
        can = "✅" if free >= cost else "❌"
        builder.button(
            text=f"{can} {b.emoji} {b.name} | {b.base_income}/мин | {cost}р.",
            callback_data=f"biz_select_building:{b.id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="business"))

    path_info = PATH_INFO.get(user.business_path, {})
    await cb.message.edit_text(
        f"🏗 <b>Строительство</b>\n\n"
        f"Путь: {path_info.get('emoji','')} {path_info.get('name','')}\n"
        f"Свободных районов: {free}/{total}\n\n"
        f"Выбери здание:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("biz_select_building:"))
async def cb_biz_select_building(cb: CallbackQuery, session: AsyncSession, user: User):
    """После выбора здания — выбираем город."""
    building_id = cb.data.split(":")[1]
    cfg = BUILDINGS_BY_ID.get(building_id)
    if not cfg:
        await cb.answer("Здание не найдено", show_alert=True)
        return

    # Получаем города где есть районы игрока
    from app.models.city import District, City
    result = await session.execute(
        select(City.id, City.name, City.type_id).distinct()
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
    for city_id, city_name, city_type in cities_with_districts:
        builder.button(
            text=f"🏙 {city_name} ({city_type} тип.)",
            callback_data=f"biz_build_in:{building_id}:{city_id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="biz_build"))

    await cb.message.edit_text(
        f"🏗 <b>{cfg.emoji} {cfg.name}</b>\n\n"
        f"Доход: {cfg.base_income}/мин\n"
        f"Стоимость: {cost} районов\n\n"
        f"Выбери город для строительства:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("biz_build_in:"))
async def cb_biz_build_in(cb: CallbackQuery, session: AsyncSession, user: User):
    """Строим здание в выбранном городе."""
    _, building_id, city_id_str = cb.data.split(":")
    city_id = int(city_id_str)

    result = await business_service.buy_building(
        session, user, building_id, city_id
    )
    if result["ok"]:
        cfg = BUILDINGS_BY_ID.get(building_id)
        await cb.answer(
            f"✅ {cfg.emoji if cfg else ''} {cfg.name if cfg else building_id} построено!"
        )
        await cb_business(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)