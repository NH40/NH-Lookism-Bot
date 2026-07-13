import html

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.data.fame import FAME_SETS, FAME_SET_MAP, FAME_FORGE_COST, fame_fragment_key
from app.services.fame_service import fame_service
from app.utils.formatters import fmt_num

router = Router()


# ── Админ-панель: выдача фрагментов/сетов славы ─────────────────────────────

@router.callback_query(F.data.startswith("adm_fame_menu:"))
async def cb_adm_fame_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.handlers.admin._common import is_admin
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    from app.services.admin_service import admin_service
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    owned = await fame_service.get_owned_fragments(session, found.id)
    builder = InlineKeyboardBuilder()
    lines = [f"🌟 <b>Слава</b> — {html.escape(found.full_name)}\n"]
    for s in FAME_SETS:
        if s.stub:
            continue
        count = sum(1 for f in s.fragments if fame_fragment_key(s.set_key, f.key) in owned)
        lines.append(f"📦 {s.name} [{count}/{len(s.fragments)}]")
        builder.row(InlineKeyboardButton(
            text=f"📦 {s.name} [{count}/{len(s.fragments)}]",
            callback_data=f"adm_fame_set:{tg_id}:{s.set_key}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_user:{tg_id}"))

    await cb.message.edit_text("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data.startswith("adm_fame_set:"))
async def cb_adm_fame_set(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.handlers.admin._common import is_admin
    if not is_admin(user.tg_id):
        return
    _, tg_id, set_key = cb.data.split(":")
    s = FAME_SET_MAP.get(set_key)
    if not s or s.stub:
        await cb.answer("Сет не найден", show_alert=True)
        return
    from app.services.admin_service import admin_service
    found = await admin_service.find_user(session, tg_id)
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    frags = await fame_service.get_set_fragments(session, set_key)
    owner_by_key = {f.fragment_key.split(":")[1]: f.owner_user_id for f in frags}

    lines = [f"📦 <b>{s.name}</b> — {html.escape(found.full_name)}\n"]
    builder = InlineKeyboardBuilder()
    for fdef in s.fragments:
        owner_id = owner_by_key.get(fdef.key)
        status = "✅ у него" if owner_id == found.id else ("🔒 у другого" if owner_id else "⚒ свободен")
        lines.append(f"{fdef.emoji} {fdef.name} — {status}")
        builder.row(InlineKeyboardButton(
            text=f"➕ Выдать «{fdef.name}»",
            callback_data=f"adm_fame_give:{tg_id}:{set_key}:{fdef.key}",
        ))
    builder.row(InlineKeyboardButton(
        text="➕ Выдать весь сет", callback_data=f"adm_fame_give_set:{tg_id}:{set_key}",
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_fame_menu:{tg_id}"))

    await cb.message.edit_text("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data.startswith("adm_fame_give_set:"))
async def cb_adm_fame_give_set(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.handlers.admin._common import is_admin
    if not is_admin(user.tg_id):
        return
    _, tg_id, set_key = cb.data.split(":")
    from app.services.admin_service import admin_service
    found = await admin_service.find_user(session, tg_id)
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    result = await fame_service.admin_grant_full_set(session, found, set_key)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return
    await session.commit()
    await cb.answer(f"✅ Выдан весь сет: {result['set_name']}", show_alert=True)
    await cb_adm_fame_set(cb, session, user)


@router.callback_query(F.data.startswith("adm_fame_give:"))
async def cb_adm_fame_give(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.handlers.admin._common import is_admin
    if not is_admin(user.tg_id):
        return
    _, tg_id, set_key, frag_key = cb.data.split(":")
    from app.services.admin_service import admin_service
    found = await admin_service.find_user(session, tg_id)
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    result = await fame_service.admin_grant_fragment(session, found, set_key, frag_key)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return
    await session.commit()
    await cb.answer(f"✅ Выдано: {result['name']}", show_alert=True)
    await cb_adm_fame_set(cb, session, user)


class FameTransferFSM(StatesGroup):
    waiting_target = State()


@router.callback_query(F.data == "fame_forge")
async def cb_fame_forge(cb: CallbackQuery, session: AsyncSession, user: User):
    has_any = await fame_service.has_available_fragment(session)

    lines = [
        "🔨 <b>Кузница славы</b>\n",
        f"⭐ Очки активности (Алея славы): <b>{fmt_num(user.fame_alltime_points)}</b>",
        f"💎 Цена фрагмента: <b>{FAME_FORGE_COST}</b> очков\n",
    ]

    builder = InlineKeyboardBuilder()

    if not has_any:
        lines.append("🔒 <b>Все фрагменты всех сетов уже выкованы!</b>\n<i>Идей для формирования новых сетов пока нет.</i>")
    else:
        lines.append("Выбери сет, чтобы посмотреть части и выковать свободную:")
        for s in FAME_SETS:
            if s.stub:
                builder.button(text=f"🔒 {s.name} (скоро)", callback_data="noop")
            else:
                owned = await fame_service.get_owned_fragments(session, user.id)
                count = sum(1 for f in s.fragments if fame_fragment_key(s.set_key, f.key) in owned)
                builder.button(text=f"📦 {s.name} [{count}/{len(s.fragments)}]", callback_data=f"fame_set:{s.set_key}")
        builder.adjust(1)

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="titles"))

    text = "\n".join(lines)
    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("fame_set:"))
async def cb_fame_set_detail(cb: CallbackQuery, session: AsyncSession, user: User):
    set_key = cb.data.split(":")[1]
    s = FAME_SET_MAP.get(set_key)
    if not s or s.stub:
        await cb.answer("Сет пока недоступен", show_alert=True)
        return

    frags = await fame_service.get_set_fragments(session, set_key)
    frag_by_key = {f.fragment_key.split(":")[1]: f for f in frags}

    lines = [
        f"📦 <b>{s.name}</b>\n",
        f"🎁 Бонус сета: <b>{s.bonus_name}</b>\n{s.bonus_description}\n",
        "━━━ 🧩 Части сета ━━━",
    ]

    builder = InlineKeyboardBuilder()
    owned_count = 0
    for fdef in s.fragments:
        row = frag_by_key.get(fdef.key)
        if row and row.owner_user_id:
            if row.owner_user_id == user.id:
                lines.append(f"✅ {fdef.emoji} <b>{fdef.name}</b> — у тебя\n   └ {fdef.description}")
                owned_count += 1
            else:
                owner = await session.get(User, row.owner_user_id)
                owner_name = html.escape(owner.full_name) if owner else "?"
                lines.append(f"🔒 {fdef.emoji} <b>{fdef.name}</b> — у игрока {owner_name}\n   └ {fdef.description}")
        else:
            can_afford = "✅" if (user.fame_alltime_points or 0) >= FAME_FORGE_COST else "❌"
            lines.append(f"⚒ {fdef.emoji} <b>{fdef.name}</b> — свободен\n   └ {fdef.description}")
            builder.row(InlineKeyboardButton(
                text=f"{can_afford} ⚒ Выковать {fdef.name} — {FAME_FORGE_COST}",
                callback_data=f"fame_forge_do:{set_key}:{fdef.key}",
            ))

    if owned_count > 0:
        builder.row(InlineKeyboardButton(text="🎁 Передать", callback_data=f"fame_transfer_menu:{set_key}"))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="fame_forge"))

    text = "\n".join(lines)
    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("fame_forge_do:"))
async def cb_fame_forge_do(cb: CallbackQuery, session: AsyncSession, user: User):
    _, set_key, frag_key = cb.data.split(":")

    from app.services.cooldown_service import cooldown_service
    lock_key = f"lock:fame_forge:{user.id}"
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подождите...", show_alert=False)
        return

    result = await fame_service.forge_fragment(session, user, set_key, frag_key)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    await session.commit()
    await cb.answer(f"✅ Выковано: {result['name']} ({result['set_name']})!", show_alert=True)
    await cb_fame_set_detail(cb, session, user)


@router.callback_query(F.data.startswith("fame_transfer_menu:"))
async def cb_fame_transfer_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    set_key = cb.data.split(":")[1]
    s = FAME_SET_MAP.get(set_key)
    if not s or s.stub:
        await cb.answer("Сет не найден", show_alert=True)
        return

    owned = await fame_service.get_owned_fragments(session, user.id)
    my_frags = [f for f in s.fragments if fame_fragment_key(set_key, f.key) in owned]

    builder = InlineKeyboardBuilder()
    for fdef in my_frags:
        builder.row(InlineKeyboardButton(
            text=f"{fdef.emoji} Передать «{fdef.name}»",
            callback_data=f"fame_transfer_frag:{set_key}:{fdef.key}",
        ))
    if len(my_frags) == len(s.fragments):
        builder.row(InlineKeyboardButton(text="📦 Передать весь сет", callback_data=f"fame_transfer_full:{set_key}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"fame_set:{set_key}"))

    await cb.message.edit_text(
        f"🎁 <b>Передача — {s.name}</b>\n\nВыбери, что передать:",
        reply_markup=builder.as_markup(), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("fame_transfer_frag:"))
async def cb_fame_transfer_frag(cb: CallbackQuery, state: FSMContext):
    _, set_key, frag_key = cb.data.split(":")
    await state.set_state(FameTransferFSM.waiting_target)
    await state.update_data(mode="fragment", set_key=set_key, frag_key=frag_key)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"fame_set:{set_key}"))
    await cb.message.edit_text(
        "🎁 <b>Передача фрагмента</b>\n\nВведи <b>@username</b> или <b>tg_id</b> получателя:",
        reply_markup=builder.as_markup(), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("fame_transfer_full:"))
async def cb_fame_transfer_full(cb: CallbackQuery, state: FSMContext):
    set_key = cb.data.split(":")[1]
    await state.set_state(FameTransferFSM.waiting_target)
    await state.update_data(mode="full_set", set_key=set_key)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"fame_set:{set_key}"))
    await cb.message.edit_text(
        "📦 <b>Передача всего сета</b>\n\nВведи <b>@username</b> или <b>tg_id</b> получателя:",
        reply_markup=builder.as_markup(), parse_mode="HTML",
    )


@router.message(FameTransferFSM.waiting_target)
async def msg_fame_transfer_target(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    query = (message.text or "").strip().lstrip("@")

    from app.services.admin_service import admin_service
    target = await admin_service.find_user(session, query)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К титулам", callback_data="titles"))

    if not target:
        await message.answer("❌ Игрок не найден.", reply_markup=builder.as_markup())
        return

    set_key = data.get("set_key")
    if data.get("mode") == "full_set":
        result = await fame_service.transfer_full_set(session, user, target, set_key)
    else:
        result = await fame_service.transfer_fragment(session, user, target, set_key, data.get("frag_key"))

    if not result["ok"]:
        await session.rollback()
        await message.answer(f"❌ {result['reason']}", reply_markup=builder.as_markup())
        return

    await session.commit()

    from app.bot_instance import get_bot
    bot = get_bot()
    what = result.get("set_name") if data.get("mode") == "full_set" else result.get("name")
    try:
        await bot.send_message(
            target.tg_id,
            f"🎁 <b>{html.escape(user.full_name)}</b> передал(а) тебе: <b>{what}</b> (Кузница славы)!",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await message.answer(
        f"✅ Передано игроку {html.escape(target.full_name)}: {what}",
        reply_markup=builder.as_markup(), parse_mode="HTML",
    )
