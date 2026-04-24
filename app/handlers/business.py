from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.building import UserBuilding
from app.models.city import District, City
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
        "desc": "Стабильный доход, не влияет на влияние",
        "color": "🟢",
    },
    "illegal": {
        "name": "Нелегальный",
        "emoji": "🕶",
        "desc": "−Влияние при постройке, но больше дохода",
        "color": "🔴",
    },
    "political": {
        "name": "Политика",
        "emoji": "🏛",
        "desc": "+Влияние при постройке",
        "color": "🔵",
    },
}


async def _show_business_main(
    cb: CallbackQuery, session: AsyncSession, user: User
) -> None:
    info = await business_service.get_income_breakdown(session, user)
    path_info = PATH_INFO.get(user.business_path, {})

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🏗 Построить здание", callback_data="biz_build"
    ))
    builder.row(InlineKeyboardButton(
        text="🏢 Мои здания", callback_data="biz_my_buildings"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Главное меню", callback_data="main_menu"
    ))

    bonuses = []
    if info['total_bonus_percent']:
        bonuses.append(f"  📈 Бонус: +{info['total_bonus_percent']}%")
    if info['potion_bonus']:
        bonuses.append(f"  🧪 Зелье: +{info['potion_bonus']}%")
    if info['district_multiplier'] != 1.0:
        bonuses.append(f"  ×{info['district_multiplier']:.1f} мультипликатор")
    bonus_str = ("\n" + "\n".join(bonuses)) if bonuses else ""

    influence_note = ""
    if user.business_path == "illegal":
        influence_note = "\n⚠️ Нелегальный путь: −влияние за постройку"
    elif user.business_path == "political":
        influence_note = "\n✅ Политика: +влияние за постройку"

    try:
        await cb.message.edit_text(
            f"🏢 <b>Бизнес</b>\n\n"
            f"📍 Путь: {path_info.get('color','')} {path_info.get('emoji','')} {path_info.get('name','')}"
            f"{influence_note}\n"
            f"{'─'*22}\n"
            f"💰 Базовый доход: {fmt_num(info['base_income'])}/мин\n"
            f"📈 Итого: {fmt_num(info['final_income'])}/мин"
            + bonus_str,
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "business")
async def cb_business(cb: CallbackQuery, session: AsyncSession, user: User):
    if not user.business_path:
        builder = InlineKeyboardBuilder()
        for path_id, info in PATH_INFO.items():
            builder.button(
                text=f"{info['color']} {info['emoji']} {info['name']}",
                callback_data=f"biz_path:{path_id}"
            )
        builder.adjust(1)
        builder.row(InlineKeyboardButton(
            text="◀️ Назад", callback_data="main_menu"
        ))
        try:
            await cb.message.edit_text(
                "🏢 <b>Бизнес — Выбор пути</b>\n\n"
                "🟢 ⚖️ <b>Легальный</b>\n"
                "  Стабильный доход, влияние не меняется\n\n"
                "🔴 🕶 <b>Нелегальный</b>\n"
                "  −Влияние при постройке, +доход больше\n\n"
                "🔵 🏛 <b>Политика</b>\n"
                "  +Влияние при постройке\n\n"
                "⚠️ <i>Выбор нельзя изменить до гибели!</i>",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    await _show_business_main(cb, session, user)


@router.callback_query(F.data.startswith("biz_path:"))
async def cb_biz_path(cb: CallbackQuery, session: AsyncSession, user: User):
    path = cb.data.split(":")[1]
    if user.business_path:
        await cb.answer("Путь уже выбран", show_alert=True)
        return
    user.business_path = path
    await session.flush()
    path_info = PATH_INFO.get(path, {})
    await cb.answer(f"✅ {path_info.get('name','')} выбран!")
    await _show_business_main(cb, session, user)


@router.callback_query(F.data == "biz_my_buildings")
async def cb_biz_my_buildings(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    buildings = await building_repo.get_user_buildings(session, user.id)

    if not buildings:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="🏗 Построить первое здание", callback_data="biz_build"
        ))
        builder.row(InlineKeyboardButton(
            text="◀️ Назад", callback_data="business"
        ))
        try:
            await cb.message.edit_text(
                "🏢 <b>Мои здания</b>\n\n"
                "У тебя пока нет зданий.\nПострой первое!",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    info = await business_service.get_income_breakdown(session, user)

    # Группируем по city_id
    city_buildings: dict[int, list] = {}
    for b in buildings:
        key = b.city_id or 0
        city_buildings.setdefault(key, []).append(b)

    builder = InlineKeyboardBuilder()
    for city_id, city_blds in city_buildings.items():
        if city_id:
            city = await city_repo.get_city(session, city_id)
            city_name = city.name if city else f"Город {city_id}"
        else:
            city_name = "Без города"
        total_income = sum(b.base_income * b.count for b in city_blds)
        builder.button(
            text=f"🏙 {city_name} | 💰 {fmt_num(total_income)}/мин",
            callback_data=f"biz_city:{city_id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="🏗 Построить ещё", callback_data="biz_build"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="business"
    ))

    try:
        await cb.message.edit_text(
            f"🏢 <b>Мои здания</b>\n\n"
            f"💰 Базовый доход: {fmt_num(info['base_income'])}/мин\n"
            f"📈 Итого: {fmt_num(info['final_income'])}/мин\n\n"
            f"Выбери город:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("biz_city:"))
async def cb_biz_city(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    city_id = int(cb.data.split(":")[1])

    result = await session.execute(
        select(UserBuilding).where(
            UserBuilding.user_id == user.id,
            UserBuilding.city_id == (city_id if city_id else None),
            UserBuilding.is_active == True,
        )
    )
    buildings = result.scalars().all()

    city_name = "Без города"
    districts_in_city = 0
    if city_id:
        city = await city_repo.get_city(session, city_id)
        city_name = city.name if city else f"Город {city_id}"
        districts_in_city = await session.scalar(
            select(func.count(District.id)).where(
                District.owner_id == user.id,
                District.city_id == city_id,
                District.is_captured == True,
            )
        ) or 0

    used_districts = await session.scalar(
        select(func.sum(UserBuilding.district_cost)).where(
            UserBuilding.user_id == user.id,
            UserBuilding.city_id == (city_id if city_id else None),
            UserBuilding.is_active == True,
        )
    ) or 0

    free_districts = districts_in_city - used_districts

    lines = [
        f"🏙 <b>{city_name}</b>\n",
        f"🏘 Районов: {districts_in_city} | Занято: {used_districts} | Свободно: {free_districts}\n",
        f"{'─'*22}\n",
    ]

    if not buildings:
        lines.append("Зданий нет")
    else:
        for b in buildings:
            cfg = BUILDINGS_BY_ID.get(b.building_type)
            name = cfg.name if cfg else b.building_type
            emoji = cfg.emoji if cfg else "🏢"
            income = b.base_income * b.count
            lines.append(
                f"{emoji} <b>{name}</b> ×{b.count}\n"
                f"  💰 {fmt_num(income)}/мин | 🏘 {b.district_cost}р.\n"
            )

    builder = InlineKeyboardBuilder()
    for b in buildings:
        cfg = BUILDINGS_BY_ID.get(b.building_type)
        name = cfg.name if cfg else b.building_type
        emoji = cfg.emoji if cfg else "🏢"
        builder.row(InlineKeyboardButton(
            text=f"🔨 Снести {emoji} {name} ×{b.count}",
            callback_data=f"biz_demolish:{b.id}:{city_id}"
        ))
    builder.row(InlineKeyboardButton(
        text="🏗 Построить здесь", callback_data=f"biz_build_city:{city_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="biz_my_buildings"
    ))

    try:
        await cb.message.edit_text(
            "".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("biz_demolish:"))
async def cb_biz_demolish(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    parts = cb.data.split(":")
    building_id = int(parts[1])
    city_id = int(parts[2]) if len(parts) > 2 else 0

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

    if building.count > 1:
        cost_per = building.district_cost // building.count
        building.count -= 1
        building.district_cost -= cost_per
    else:
        building.is_active = False
        building.count = 0

    await session.flush()
    await business_service._recalc_income(session, user)
    await cb.answer("🔨 Здание снесено!")

    # Показываем город напрямую — без изменения cb.data
    await _show_city_buildings(cb.message, session, user, city_id)


async def _show_city_buildings(
    message, session: AsyncSession, user: User, city_id: int
) -> None:
    """Отдельная функция отрисовки города — не трогает cb.data."""
    result = await session.execute(
        select(UserBuilding).where(
            UserBuilding.user_id == user.id,
            UserBuilding.city_id == (city_id if city_id else None),
            UserBuilding.is_active == True,
        )
    )
    buildings = result.scalars().all()

    city_name = "Без города"
    districts_in_city = 0
    if city_id:
        city = await city_repo.get_city(session, city_id)
        city_name = city.name if city else f"Город {city_id}"
        districts_in_city = await session.scalar(
            select(func.count(District.id)).where(
                District.owner_id == user.id,
                District.city_id == city_id,
                District.is_captured == True,
            )
        ) or 0

    used_districts = await session.scalar(
        select(func.sum(UserBuilding.district_cost)).where(
            UserBuilding.user_id == user.id,
            UserBuilding.city_id == (city_id if city_id else None),
            UserBuilding.is_active == True,
        )
    ) or 0

    free_districts = districts_in_city - used_districts

    lines = [
        f"🏙 <b>{city_name}</b>\n",
        f"🏘 Районов: {districts_in_city} | Занято: {used_districts} | Свободно: {free_districts}\n",
        f"{'─'*22}\n",
    ]

    if not buildings:
        lines.append("Зданий нет")
    else:
        for b in buildings:
            cfg = BUILDINGS_BY_ID.get(b.building_type)
            name = cfg.name if cfg else b.building_type
            emoji = cfg.emoji if cfg else "🏢"
            income = b.base_income * b.count
            lines.append(
                f"{emoji} <b>{name}</b> ×{b.count}\n"
                f"  💰 {fmt_num(income)}/мин | 🏘 {b.district_cost}р.\n"
            )

    builder = InlineKeyboardBuilder()
    for b in buildings:
        cfg = BUILDINGS_BY_ID.get(b.building_type)
        name = cfg.name if cfg else b.building_type
        emoji = cfg.emoji if cfg else "🏢"
        builder.row(InlineKeyboardButton(
            text=f"🔨 Снести {emoji} {name} ×{b.count}",
            callback_data=f"biz_demolish:{b.id}:{city_id}"
        ))
    builder.row(InlineKeyboardButton(
        text="🏗 Построить здесь", callback_data=f"biz_build_city:{city_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="biz_my_buildings"
    ))

    try:
        await message.edit_text(
            "".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


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
    free = total - used

    builder = InlineKeyboardBuilder()
    for b in buildings:
        discount = user.building_discount_percent
        cost = max(1, int(b.district_cost * (1 - discount / 100)))
        can = "✅" if free >= cost else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can} {b.emoji} {b.name} | 💰 {fmt_num(b.base_income)}/мин | 🏘 {cost}р.",
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
    """Строительство в конкретном городе — выбор здания."""
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

    used_in_city = await session.scalar(
        select(func.sum(UserBuilding.district_cost)).where(
            UserBuilding.user_id == user.id,
            UserBuilding.city_id == city_id,
            UserBuilding.is_active == True,
        )
    ) or 0

    free = districts_in_city - used_in_city

    builder = InlineKeyboardBuilder()
    for b in buildings:
        discount = user.building_discount_percent
        cost = max(1, int(b.district_cost * (1 - discount / 100)))
        can = "✅" if free >= cost else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can} {b.emoji} {b.name} | 💰 {fmt_num(b.base_income)}/мин | 🏘 {cost}р.",
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

    # Города где есть районы
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
    for city_id, city_name in cities_with_districts:
        free = await session.scalar(
            select(func.count(District.id)).where(
                District.owner_id == user.id,
                District.city_id == city_id,
                District.is_captured == True,
            )
        ) or 0
        used = await session.scalar(
            select(func.sum(UserBuilding.district_cost)).where(
                UserBuilding.user_id == user.id,
                UserBuilding.city_id == city_id,
                UserBuilding.is_active == True,
            )
        ) or 0
        free_in_city = free - used
        can = "✅" if free_in_city >= cost else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can} 🏙 {city_name} | 🏘 свободно: {free_in_city}",
            callback_data=f"biz_build_in:{building_id}:{city_id}"
        ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="biz_build"
    ))

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