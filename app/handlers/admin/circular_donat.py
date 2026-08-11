"""
Администраторский интерфейс управления круговыми донатами.

Флоу:
  admin_user_kb → кнопка "🔄 Круговые донаты" (adm_circ_menu:{tg_id})
  → список донатов с текущим количеством кругов
  → нажать донат → показать детали + кнопки [+Круг] [−Круг]
  → для Архангела: кнопка "♟ Выдать сверх круг" (игнорирует лимит)
  → для админа: кнопки массовой выдачи +1, +5, +10, ✏️ Свой
  → ✏️ Свой: положительное число → добавить, отрицательное → убрать
"""
import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.admin_service import admin_service
from app.services.circular_donat_service import add_circle, remove_circle, get_user_circles
from app.data.titles import CIRCULAR_DONATS, CIRCULAR_DONAT_MAP
from app.handlers.admin._common import is_admin

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

    await _render_circ_detail(cb.message, session, tg_id, donat_id, found)
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
    found2 = await admin_service.find_user(session, str(tg_id))
    await _render_circ_detail(cb.message, session, tg_id, donat_id, found2)


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
    await _render_circ_detail(cb.message, session, tg_id, donat_id, found2)


# ── СВЕРХ КРУГИ АРХАНГЕЛА (админская выдача, игнорирует лимиты) ────────────

@router.callback_query(F.data.startswith("adm_circ_archangel_infinite:"))
async def cb_adm_circ_archangel_infinite(cb: CallbackQuery, session: AsyncSession, user: User):
    """Админ: принудительно добавляет 1 сверх круг Архангела (игнорируя условия)."""
    if not is_admin(user.tg_id):
        return
    
    parts = cb.data.split(":")
    tg_id = int(parts[1])

    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    # Добавляем круг с force=True (игнорирует все лимиты)
    result = await add_circle(session, found, "archangel", force=True)
    await session.commit()

    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    await cb.answer(
        f"♟ Выдан сверх круг Архангела! Всего: {result['circles']} кругов",
        show_alert=True,
    )
    found2 = await admin_service.find_user(session, str(tg_id))
    await _render_circ_detail(cb.message, session, tg_id, "archangel", found2)


# ── МАССОВАЯ ВЫДАЧА КРУГОВ (АДМИН) ──────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_circ_add_bulk:"))
async def cb_adm_circ_add_bulk(cb: CallbackQuery, session: AsyncSession, user: User):
    """Админ: выдать 1, 5 или 10 кругов сразу."""
    if not is_admin(user.tg_id):
        return
    
    parts = cb.data.split(":")
    tg_id = int(parts[1])
    donat_id = parts[2]
    count = int(parts[3])

    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    d = CIRCULAR_DONAT_MAP.get(donat_id)
    if not d:
        await cb.answer("Донат не найден", show_alert=True)
        return

    added = 0
    for _ in range(count):
        result = await add_circle(session, found, donat_id, force=True)
        if result.get("ok"):
            added += 1
        else:
            break
    
    await session.commit()
    
    if added > 0:
        await cb.answer(
            f"✅ Добавлено {added} кругов {d.emoji} {d.name}!",
            show_alert=True,
        )
    else:
        await cb.answer("❌ Не удалось добавить круги", show_alert=True)
    
    found2 = await admin_service.find_user(session, str(tg_id))
    await _render_circ_detail(cb.message, session, tg_id, donat_id, found2)


@router.callback_query(F.data.startswith("adm_circ_add_custom:"))
async def cb_adm_circ_add_custom(cb: CallbackQuery, session: AsyncSession, user: User):
    """Админ: запросить количество кругов для выдачи."""
    if not is_admin(user.tg_id):
        return
    
    parts = cb.data.split(":")
    tg_id = int(parts[1])
    donat_id = parts[2]

    d = CIRCULAR_DONAT_MAP.get(donat_id)
    if not d:
        await cb.answer("Донат не найден", show_alert=True)
        return

    # Сохраняем контекст в Redis на 60 секунд
    from app.services.cooldown_service import cooldown_service
    key = f"adm_circ_custom:{cb.from_user.id}"
    await cooldown_service.redis.setex(
        key,
        60,
        f"{tg_id}:{donat_id}"
    )
    
    await cb.message.answer(
        f"✏️ Введите количество кругов {d.emoji} {d.name}\n"
        f"• Положительное число → добавить круги\n"
        f"• Отрицательное число → убрать круги (по модулю)\n"
        f"• Максимум: 100\n"
        f"• 'отмена' для отмены"
    )
    await cb.answer()


@router.message(F.text)
async def handle_circ_custom_input(message: Message, session: AsyncSession, user: User):
    """Обработка ввода количества кругов (положительные - добавляем, отрицательные - убираем)."""
    if not is_admin(user.tg_id):
        return
    
    # Проверяем, есть ли контекст
    from app.services.cooldown_service import cooldown_service
    key = f"adm_circ_custom:{user.tg_id}"
    data = await cooldown_service.redis.get(key)
    if not data:
        return
    
    if message.text.lower() in ["отмена", "cancel"]:
        await cooldown_service.redis.delete(key)
        await message.answer("✅ Отменено")
        return
    
    try:
        count = int(message.text.strip())
        if count == 0:
            await message.answer("❌ Введите число не равное 0")
            return
        if abs(count) > 100:
            await message.answer("❌ Максимум 100 кругов за раз (по модулю)")
            return
    except ValueError:
        await message.answer("❌ Введите число")
        return
    
    # Получаем контекст
    tg_id_str, donat_id = data.decode().split(":")
    tg_id = int(tg_id_str)
    
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await message.answer("❌ Пользователь не найден")
        await cooldown_service.redis.delete(key)
        return
    
    d = CIRCULAR_DONAT_MAP.get(donat_id)
    if not d:
        await message.answer("❌ Донат не найден")
        await cooldown_service.redis.delete(key)
        return
    
    # ── ЛОГИКА: положительные → добавляем, отрицательные → убираем ──
    if count > 0:
        # Добавляем круги
        added = 0
        last_result = None
        for _ in range(count):
            result = await add_circle(session, found, donat_id, force=True)
            last_result = result
            if result.get("ok"):
                added += 1
            else:
                break
        
        await session.commit()
        await cooldown_service.redis.delete(key)
        
        if added > 0:
            await message.answer(f"✅ Добавлено {added} кругов {d.emoji} {d.name} для {found.full_name}!")
        else:
            reason = last_result.get('reason', 'неизвестная ошибка') if last_result else 'неизвестная ошибка'
            await message.answer(f"❌ Не удалось добавить круги: {reason}")
    
    else:
        # Убираем круги (count отрицательный)
        count_abs = abs(count)
        removed = 0
        last_result = None
        
        for _ in range(count_abs):
            result = await remove_circle(session, found, donat_id)
            last_result = result
            if result.get("ok"):
                removed += 1
            else:
                break
        
        await session.commit()
        await cooldown_service.redis.delete(key)
        
        if removed > 0:
            await message.answer(f"✅ Убрано {removed} кругов {d.emoji} {d.name} для {found.full_name}!")
        else:
            reason = last_result.get('reason', 'неизвестная ошибка') if last_result else 'неизвестная ошибка'
            await message.answer(f"❌ Не удалось убрать круги: {reason}")


# ── Рендер детального экрана ─────────────────────────────────────────────────

async def _render_circ_detail(message, session: AsyncSession, tg_id: int, donat_id: str, found) -> None:
    """Перерисовывает детальный экран после изменения кругов."""
    d = CIRCULAR_DONAT_MAP.get(donat_id)
    if not d or not found:
        return

    circles_map = await get_user_circles(session, found.id)
    n = circles_map.get(donat_id, 0)

    builder = InlineKeyboardBuilder()
    
    # ── Быстрая выдача (админ) ──────────────────────────────────────────────────
    builder.row(
        InlineKeyboardButton(text=f"➕+1", callback_data=f"adm_circ_add_bulk:{tg_id}:{donat_id}:1"),
        InlineKeyboardButton(text=f"➕+5", callback_data=f"adm_circ_add_bulk:{tg_id}:{donat_id}:5"),
        InlineKeyboardButton(text=f"➕+10", callback_data=f"adm_circ_add_bulk:{tg_id}:{donat_id}:10"),
        InlineKeyboardButton(text=f"✏️ Свой", callback_data=f"adm_circ_add_custom:{tg_id}:{donat_id}"),
    )

    # ── Обычная кнопка добавления круга (с учётом лимита) ──────────────────────
    if n < d.max_circles:
        builder.row(InlineKeyboardButton(
            text=f"➕ Добавить круг ({n} → {n + 1})",
            callback_data=f"adm_circ_add:{tg_id}:{donat_id}",
        ))
    else:
        builder.row(InlineKeyboardButton(text=f"✅ Максимум ({d.max_circles})", callback_data="noop"))

    # ── Кнопка "Сверх круг" — только для Архангела ─────────────────────────────
    if donat_id == "archangel":
        builder.row(InlineKeyboardButton(
            text=f"♟ Выдать сверх круг (бесконечно) — {n + 1}",
            callback_data=f"adm_circ_archangel_infinite:{tg_id}",
        ))

    if n > 0:
        builder.row(InlineKeyboardButton(
            text=f"➖ Убрать круг ({n} → {n - 1})",
            callback_data=f"adm_circ_rem:{tg_id}:{donat_id}",
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_circ_menu:{tg_id}"))

    # Показываем max как "∞" если у игрока уже открыты бесконечные круги
    max_display = d.max_circles
    if donat_id == "archangel" and getattr(d, "infinite_after_all", False):
        from app.repositories.title_repo import title_repo
        has_all_sets = await title_repo.has_all_sets(session, found.id)
        user_circles = await get_user_circles(session, found.id)
        all_circular_done = True
        for d_id, d_cfg in CIRCULAR_DONAT_MAP.items():
            if d_id == "archangel":
                continue
            if user_circles.get(d_id, 0) < d_cfg.max_circles:
                all_circular_done = False
                break
        if has_all_sets and all_circular_done:
            max_display = "∞"

    lines = [
        f"{d.emoji} <b>{d.name}</b>",
        f"👤 Игрок: {html.escape(found.full_name)}",
        f"🔄 Кругов: <b>{n}/{max_display}</b>",
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