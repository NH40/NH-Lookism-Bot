"""
Администраторский интерфейс управления круговыми донатами.

Флоу:
  admin_user_kb → кнопка "🔄 Круговые донаты" (adm_circ_menu:{tg_id})
  → список донатов с текущим количеством кругов
  → нажать донат → показать детали + кнопки [+Круг] [−Круг]
"""
import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.admin_service import admin_service
from app.services.circular_donat_service import add_circle, remove_circle, get_user_circles
from app.data.titles import CIRCULAR_DONATS, CIRCULAR_DONAT_MAP
from app.handlers.admin._common import is_admin, _show_user_card

router = Router()


async def _show_circ_menu(message, session: AsyncSession, tg_id: int, found) -> None:
    circles_map = await get_user_circles(session, found.id)
    builder = InlineKeyboardBuilder()
    for d in CIRCULAR_DONATS:
        n = circles_map.get(d.donat_id, 0)
        label = f"{d.emoji} {d.name} — {n}/{d.max_circles} кругов"
        builder.row(InlineKeyboardButton(
            text=label,
            callback_data=f"adm_circ_detail:{tg_id}:{d.donat_id}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_user:{tg_id}"))

    lines = [f"🔄 <b>Круговые донаты</b> — {html.escape(found.full_name)}\n"]
    for d in CIRCULAR_DONATS:
        n = circles_map.get(d.donat_id, 0)
        if n:
            lines.append(f"  {d.emoji} {d.name}: {n}/{d.max_circles}")
    if len(lines) == 1:
        lines.append("  <i>Нет активных кругов</i>")

    try:
        await message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_circ_menu:"))
async def cb_adm_circ_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    await _show_circ_menu(cb.message, session, tg_id, found)
    await cb.answer()


@router.callback_query(F.data.startswith("adm_circ_detail:"))
async def cb_adm_circ_detail(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id = int(parts[1])
    donat_id = parts[2]

    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    d = CIRCULAR_DONAT_MAP.get(donat_id)
    if not d:
        await cb.answer("Донат не найден", show_alert=True)
        return

    circles_map = await get_user_circles(session, found.id)
    n = circles_map.get(donat_id, 0)

    builder = InlineKeyboardBuilder()
    if n < d.max_circles:
        builder.row(InlineKeyboardButton(
            text=f"➕ Добавить круг ({n} → {n + 1})",
            callback_data=f"adm_circ_add:{tg_id}:{donat_id}",
        ))
    else:
        builder.row(InlineKeyboardButton(text=f"✅ Максимум ({d.max_circles})", callback_data="noop"))

    if n > 0:
        builder.row(InlineKeyboardButton(
            text=f"➖ Убрать круг ({n} → {n - 1})",
            callback_data=f"adm_circ_rem:{tg_id}:{donat_id}",
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_circ_menu:{tg_id}"))

    lines = [
        f"{d.emoji} <b>{d.name}</b>",
        f"👤 Игрок: {html.escape(found.full_name)}",
        f"🔄 Кругов: <b>{n}/{d.max_circles}</b>",
        f"💰 Цена: {d.price_per_circle}₽/круг",
        f"\n<b>Бонус за круг:</b> {d.circle_bonus}",
    ]
    if d.special_bonuses:
        lines.append("\n<b>Особые бонусы:</b>")
        for circle_n, bonus_desc in d.special_bonuses:
            mark = "✅" if n >= circle_n else "🔒"
            lines.append(f"  {mark} Круг {circle_n}: {bonus_desc}")

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("adm_circ_add:"))
async def cb_adm_circ_add(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id = int(parts[1])
    donat_id = parts[2]

    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    result = await add_circle(session, found, donat_id)
    await session.commit()

    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    d = CIRCULAR_DONAT_MAP.get(donat_id)
    await cb.answer(
        f"✅ {d.emoji} {d.name}: {result['circles']}/{d.max_circles} кругов",
        show_alert=True,
    )
    # Обновляем детальный экран
    await cb.data.__class__  # no-op to avoid lint warning
    # Обновляем found из сессии (данные изменились)
    found2 = await admin_service.find_user(session, str(tg_id))
    await _show_circ_detail(cb.message, session, tg_id, donat_id, found2)


@router.callback_query(F.data.startswith("adm_circ_rem:"))
async def cb_adm_circ_rem(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id = int(parts[1])
    donat_id = parts[2]

    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    result = await remove_circle(session, found, donat_id)
    await session.commit()

    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    d = CIRCULAR_DONAT_MAP.get(donat_id)
    await cb.answer(
        f"✅ {d.emoji} {d.name}: {result['circles']}/{d.max_circles} кругов",
        show_alert=True,
    )
    found2 = await admin_service.find_user(session, str(tg_id))
    await _show_circ_detail(cb.message, session, tg_id, donat_id, found2)


async def _show_circ_detail(message, session: AsyncSession, tg_id: int, donat_id: str, found) -> None:
    """Перерисовывает детальный экран после изменения кругов."""
    d = CIRCULAR_DONAT_MAP.get(donat_id)
    if not d or not found:
        return

    circles_map = await get_user_circles(session, found.id)
    n = circles_map.get(donat_id, 0)

    builder = InlineKeyboardBuilder()
    if n < d.max_circles:
        builder.row(InlineKeyboardButton(
            text=f"➕ Добавить круг ({n} → {n + 1})",
            callback_data=f"adm_circ_add:{tg_id}:{donat_id}",
        ))
    else:
        builder.row(InlineKeyboardButton(text=f"✅ Максимум ({d.max_circles})", callback_data="noop"))

    if n > 0:
        builder.row(InlineKeyboardButton(
            text=f"➖ Убрать круг ({n} → {n - 1})",
            callback_data=f"adm_circ_rem:{tg_id}:{donat_id}",
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_circ_menu:{tg_id}"))

    lines = [
        f"{d.emoji} <b>{d.name}</b>",
        f"👤 Игрок: {html.escape(found.full_name)}",
        f"🔄 Кругов: <b>{n}/{d.max_circles}</b>",
        f"💰 Цена: {d.price_per_circle}₽/круг",
        f"\n<b>Бонус за круг:</b> {d.circle_bonus}",
    ]
    if d.special_bonuses:
        lines.append("\n<b>Особые бонусы:</b>")
        for circle_n, bonus_desc in d.special_bonuses:
            mark = "✅" if n >= circle_n else "🔒"
            lines.append(f"  {mark} Круг {circle_n}: {bonus_desc}")

    try:
        await message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
