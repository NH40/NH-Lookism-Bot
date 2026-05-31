from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.building import UserBuilding
from app.models.city import District
from app.services.business_service import business_service
from app.repositories.building_repo import building_repo
from app.repositories.city_repo import city_repo
from app.utils.formatters import fmt_num
from app.data.buildings import BUILDINGS_BY_ID
from ._common import _show_business_main

router = Router()


def _buildings_empty_kb() -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏗 Построить первое здание", callback_data="biz_build"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="business"))
    return builder.as_markup()


@router.callback_query(F.data == "biz_my_buildings")
async def cb_biz_my_buildings(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    buildings = await building_repo.get_user_buildings(session, user.id)

    if not buildings:
        try:
            await cb.message.edit_text(
                "🏢 <b>Мои здания</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "У вас пока нет зданий.\n"
                "Постройте первое, чтобы начать получать доход!",
                reply_markup=_buildings_empty_kb(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    info = await business_service.get_income_breakdown(session, user)

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
        bld_count = sum(b.count for b in city_blds)
        builder.button(
            text=f"🏙 {city_name}  ·  {bld_count} зд.  ·  {fmt_num(total_income)}/мин",
            callback_data=f"biz_city:{city_id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🏗 Построить ещё", callback_data="biz_build"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="business"))

    try:
        await cb.message.edit_text(
            f"🏢 <b>Мои здания</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Базовый доход:  <b>{fmt_num(info['base_income'])}/мин</b>\n"
            f"📈 Итоговый доход: <b>{fmt_num(info['final_income'])}/мин</b>\n\n"
            f"Выберите город для просмотра зданий:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


async def _show_city_buildings(
    message, session: AsyncSession, user: User, city_id: int
) -> None:
    buildings = await building_repo.get_city_buildings(session, user.id, city_id)

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

    used_districts = await building_repo.get_used_districts_in_city(
        session, user.id, city_id
    )
    free_districts = max(0, districts_in_city - used_districts)

    lines = [
        f"🏙 <b>{city_name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏘 Районов: {districts_in_city}  "
        f"·  Занято: {used_districts}  "
        f"·  Свободно: <b>{free_districts}</b>\n"
    ]

    if not buildings:
        lines.append("\nЗданий нет")
    else:
        lines.append("")
        for b in buildings:
            cfg = BUILDINGS_BY_ID.get(b.building_type)
            name = cfg.name if cfg else b.building_type
            emoji = cfg.emoji if cfg else "🏢"
            income = b.base_income * b.count
            lines.append(
                f"{emoji} <b>{name}</b>"
                + (f" ×{b.count}" if b.count > 1 else "") + "\n"
                f"  💰 {fmt_num(income)}/мин  ·  🏘 {b.district_cost} р.\n"
            )

    builder = InlineKeyboardBuilder()
    for b in buildings:
        cfg = BUILDINGS_BY_ID.get(b.building_type)
        name = cfg.name if cfg else b.building_type
        emoji = cfg.emoji if cfg else "🏢"
        builder.row(InlineKeyboardButton(
            text=f"🔨 Снести {emoji} {name}" + (f" ×{b.count}" if b.count > 1 else ""),
            callback_data=f"biz_demolish:{b.id}:{city_id}"
        ))
    builder.row(InlineKeyboardButton(
        text="🏗 Построить здесь",
        callback_data=f"biz_build_city:{city_id}"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="biz_my_buildings"))

    try:
        await message.edit_text(
            "".join(lines),
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
    await _show_city_buildings(cb.message, session, user, city_id)


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
        building.district_cost = max(0, building.district_cost - cost_per)
        await session.flush()
    else:
        await session.delete(building)
        await session.flush()

    await business_service._recalc_income(session, user)
    await cb.answer("🔨 Здание снесено! Районы освобождены.")
    await _show_city_buildings(cb.message, session, user, city_id)
