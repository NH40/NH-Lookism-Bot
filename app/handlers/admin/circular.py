from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import User
from app.services.circular_donat_service import add_circle
from app.utils.admin_utils import is_admin
from app.data.titles import CIRCULAR_DONAT_MAP
from ._common import _show_circular_donat_panel, AdminFSM

router = Router()

@router.callback_query(F.data.startswith("adm_circ:"))
async def cb_adm_circ_panel(cb: CallbackQuery, session: AsyncSession):
    """Открыть панель круговых донатов"""
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔ Нет прав", show_alert=True)
        return
    
    parts = cb.data.split(":")
    tg_id = int(parts[1])
    
    from app.database.repositories.user_repo import get_user_by_tg_id
    found = await get_user_by_tg_id(session, tg_id)
    if not found:
        await cb.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    await _show_circular_donat_panel(cb.message, session, found, cb.from_user.id)
    await cb.answer()

@router.callback_query(F.data.startswith("adm_circ_add:"))
async def cb_adm_circ_add(cb: CallbackQuery, session: AsyncSession):
    """Выдать круги (1, 5 или 10)"""
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔ Нет прав", show_alert=True)
        return
    
    parts = cb.data.split(":")
    donat_id = parts[1]
    user_id = int(parts[2])
    count = int(parts[3])
    
    from app.database.repositories.user_repo import get_user_by_id
    target = await get_user_by_id(session, user_id)
    if not target:
        await cb.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    added = 0
    for _ in range(count):
        result = await add_circle(session, target, donat_id, force=True)
        if result.get("ok"):
            added += 1
        else:
            break
    
    cfg = CIRCULAR_DONAT_MAP.get(donat_id)
    if added > 0:
        await cb.answer(f"✅ Добавлено {added} кругов {cfg.emoji} {cfg.name}!", show_alert=True)
    else:
        await cb.answer("❌ Не удалось добавить круги", show_alert=True)
    
    await _show_circular_donat_panel(cb.message, session, target, cb.from_user.id)

@router.callback_query(F.data.startswith("adm_circ_add_custom:"))
async def cb_adm_circ_add_custom(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Запросить количество кругов для выдачи"""
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔ Нет прав", show_alert=True)
        return
    
    parts = cb.data.split(":")
    donat_id = parts[1]
    user_id = int(parts[2])
    
    cfg = CIRCULAR_DONAT_MAP.get(donat_id)
    if not cfg:
        await cb.answer("❌ Донат не найден", show_alert=True)
        return
    
    await state.set_state(AdminFSM.waiting_circ_count)
    await state.update_data(circ_donat_id=donat_id, circ_user_id=user_id)
    
    await cb.message.answer(
        f"✏️ Введите количество кругов {cfg.emoji} {cfg.name} для выдачи\n"
        f"(максимум 100, или 'отмена' для отмены)"
    )
    await cb.answer()

@router.message(AdminFSM.waiting_circ_count)
async def handle_circ_count_input(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ввода количества кругов"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Нет прав")
        await state.clear()
        return
    
    if message.text.lower() in ["отмена", "cancel"]:
        await state.clear()
        await message.answer("✅ Отменено")
        return
    
    try:
        count = int(message.text.strip())
        if count <= 0:
            await message.answer("❌ Количество должно быть больше 0")
            return
        if count > 100:
            await message.answer("❌ Максимум 100 кругов за раз")
            return
    except ValueError:
        await message.answer("❌ Введите число")
        return
    
    data = await state.get_data()
    donat_id = data.get("circ_donat_id")
    target_user_id = data.get("circ_user_id")
    
    if not donat_id or not target_user_id:
        await message.answer("❌ Сессия истекла")
        await state.clear()
        return
    
    from app.database.repositories.user_repo import get_user_by_id
    target = await get_user_by_id(session, target_user_id)
    if not target:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
    
    added = 0
    for _ in range(count):
        result = await add_circle(session, target, donat_id, force=True)
        if result.get("ok"):
            added += 1
        else:
            break
    
    cfg = CIRCULAR_DONAT_MAP.get(donat_id)
    if added > 0:
        await message.answer(f"✅ Добавлено {added} кругов {cfg.emoji} {cfg.name} для {target.full_name}!")
    else:
        await message.answer("❌ Не удалось добавить круги")
    
    await state.clear()