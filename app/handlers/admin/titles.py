from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.admin_service import admin_service
from app.services.title_service import title_service
from app.handlers.admin._common import (
    is_admin, _show_set_panel, _render_untitle, _render_untset
)

router = Router()


@router.callback_query(F.data.startswith("adm_title:"))
async def cb_adm_title(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    from app.utils.keyboards.admin import titles_grant_kb
    try:
        await cb.message.edit_text(
            "💎 Выберите сет:",
            reply_markup=titles_grant_kb(int(tg_id)),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_grantset:"))
async def cb_adm_grantset(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, set_id = int(parts[1]), parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    await _show_set_panel(cb.message, session, user, tg_id, set_id, found)


@router.callback_query(F.data.startswith("adm_grantset_all:"))
async def cb_adm_grantset_all(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, set_id = int(parts[1]), parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    from app.data.titles import DONAT_TITLES
    title_ids = [t.title_id for t in DONAT_TITLES if t.set_id == set_id]
    count = 0
    for tid in title_ids:
        result = await title_service.grant_title(session, found, tid, user.tg_id)
        if result["ok"]:
            count += 1
    await cb.answer(f"✅ Выдано {count} титулов!")
    await _show_set_panel(cb.message, session, user, tg_id, set_id, found)


@router.callback_query(F.data.startswith("adm_grant_title:"))
async def cb_adm_grant_title(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, title_id = int(parts[1]), parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    result = await title_service.grant_title(session, found, title_id, user.tg_id)
    if result["ok"]:
        await cb.answer(f"✅ {result['title']} выдан!")
    else:
        await cb.answer(result["reason"], show_alert=True)
    from app.data.titles import DONAT_TITLE_MAP
    cfg = DONAT_TITLE_MAP.get(title_id)
    if cfg:
        await _show_set_panel(cb.message, session, user, tg_id, cfg.set_id, found)


@router.callback_query(F.data.startswith("adm_untitle:"))
async def cb_adm_untitle(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    await _render_untitle(cb.message, session, tg_id, found)


@router.callback_query(F.data.startswith("adm_untset:"))
async def cb_adm_untset(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, set_id = int(parts[1]), parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    await _render_untset(cb.message, session, tg_id, set_id, found)


@router.callback_query(F.data.startswith("adm_revset:"))
async def cb_adm_revset(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, set_id = int(parts[1]), parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    try:
        removed = await title_service.revoke_set(session, found, set_id)
    except Exception as e:
        await cb.answer(f"Ошибка: {e}", show_alert=True)
        return
    await cb.answer(f"✅ Снято {removed} титулов", show_alert=True)
    await _render_untitle(cb.message, session, tg_id, found)


@router.callback_query(F.data.startswith("adm_revoke:"))
async def cb_adm_revoke(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id, title_id = int(parts[1]), parts[2]
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    from app.data.titles import DONAT_TITLE_MAP, DONAT_TITLES
    cfg = DONAT_TITLE_MAP.get(title_id)
    try:
        result = await title_service.revoke_title(session, found, title_id)
    except Exception as e:
        await cb.answer(f"Ошибка: {e}", show_alert=True)
        return
    if not result["ok"]:
        await cb.answer("Ошибка", show_alert=True)
        return
    await cb.answer("✅ Титул снят")
    if cfg:
        owned_after = set(await title_service.get_user_titles(session, found.id))
        remaining = [t for t in DONAT_TITLES if t.set_id == cfg.set_id and t.title_id in owned_after]
        if remaining:
            await _render_untset(cb.message, session, tg_id, cfg.set_id, found)
            return
    await _render_untitle(cb.message, session, tg_id, found)


@router.callback_query(F.data.startswith("adm_all:"))
async def cb_adm_all(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    count = await admin_service.give_all_titles(session, found, user.tg_id)
    await cb.answer(f"🔱 Выдано {count} титулов!")


@router.callback_query(F.data.startswith("adm_none:"))
async def cb_adm_none(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return
    await admin_service.remove_all_titles(session, found)
    await cb.answer("💀 Все титулы сняты!")
