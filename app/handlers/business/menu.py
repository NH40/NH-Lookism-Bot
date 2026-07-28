from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.utils.formatters import fmt_num
from app.utils.menu_media import safe_edit
from ._common import PATH_INFO, _show_business_main

router = Router()


@router.callback_query(F.data == "business")
async def cb_business(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.business_building_id:
        await _show_business_main(cb, session, user)
        return

    from app.repositories.city_repo import city_repo
    district_count = await city_repo.get_user_district_count(session, user.id)
    if district_count < 1:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
        await safe_edit(
            cb,
            "🏢 <b>Бизнес</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Сначала захвати хотя бы один район (Атака), затем сможешь"
            " выбрать своё дело здесь.",
            builder.as_markup(),
        )
        return

    from app.data.buildings import BUILDINGS, CANONICAL_BUILDING_IDS
    genius_level = user.business_genius_level

    builder = InlineKeyboardBuilder()
    for b in BUILDINGS:
        if b.id not in CANONICAL_BUILDING_IDS:
            continue
        if b.min_biz_genius * 2 > genius_level:
            continue
        path_info = PATH_INFO.get(b.path, {})
        builder.row(InlineKeyboardButton(
            text=f"{path_info.get('color', '')} {b.emoji} {b.name} — {fmt_num(b.base_income)}/район",
            callback_data=f"biz_choose:{b.id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    await safe_edit(
        cb,
        "🏢 <b>Бизнес — Выбор дела</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выбери здание — это решение нельзя изменить!\n"
        "Дальше доход будет расти от количества захваченных районов,"
        " новых зданий строить не нужно.\n\n"
        "🟢 Легальный — стабильный доход\n"
        "🔴 Нелегальный — доход выше, но волатильный, влияние падает с каждым районом\n"
        "🔵 Политика — доход ниже, но влияние растёт с каждым районом\n"
        "🟣 Цифровой — соло слабее, но сеть своих районов поднимает доход выше легального\n\n"
        "Больше зданий откроется с ростом уровня Гения бизнеса.",
        builder.as_markup(),
    )


@router.callback_query(F.data.startswith("biz_choose:"))
async def cb_biz_choose(cb: CallbackQuery, session: AsyncSession, user: User):
    building_id = cb.data.split(":", 1)[1]
    from app.services.business_service import business_service
    result = await business_service.choose_business(session, user, building_id)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return
    await cb.answer(f"✅ {result['building']} выбран!")
    await _show_business_main(cb, session, user)
