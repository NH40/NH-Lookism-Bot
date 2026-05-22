from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.services.promo_service import promo_service, REWARD_LABELS, _parse_rewards, _rewards_summary
from app.utils.keyboards.common import back_kb
from app.handlers.admin._common import is_admin, AdminFSM

router = Router()


@router.callback_query(F.data == "admin_promos")
async def cb_admin_promos(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    promos = await promo_service.get_all_promos(session)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="➕ Создать промокод", callback_data="admin_promo_create"
    ))
    for p in promos:
        status = "✅" if p.is_active else "❌"
        rewards = _parse_rewards(p)
        rewards_short = ", ".join(
            f"{REWARD_LABELS.get(r['type'], r['type'])} ×{r['amount']}"
            for r in rewards
        )
        limit_info = (
            f"{p.used_count}/{p.max_uses}"
            if p.limit_type == "uses"
            else f"до {p.expires_at.strftime('%d.%m %H:%M') if p.expires_at else '?'}"
        )
        builder.row(InlineKeyboardButton(
            text=f"{status} {p.code} | {rewards_short} ({limit_info})",
            callback_data=f"admin_promo_info:{p.id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main"))

    try:
        await cb.message.edit_text(
            f"🎁 <b>Промокоды</b>\n\nВсего: {len(promos)}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_promo_create")
async def cb_admin_promo_create(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_promo_create)

    types_str = "\n".join(f"  <code>{k}</code> — {v}" for k, v in REWARD_LABELS.items())
    try:
        await cb.message.edit_text(
            f"➕ <b>Создать промокод</b>\n\n"
            f"<b>Формат:</b>\n"
            f"<code>КОД [uses|time] МАКС_ИСП/ЧАСОВ НАГРАДА1:КОЛ ...</code>\n\n"
            f"<b>Примеры:</b>\n"
            f"<code>WELCOME uses 50 coins:100000 tickets:5</code>\n"
            f"  → 50 использований, монеты + тикеты\n\n"
            f"<code>EVENT2026 time 24 ui_fragments:200 coins:50000</code>\n"
            f"  → действует 24 часа, фрагменты + монеты\n\n"
            f"<code>PROMO uses 1 mastery_points:10</code>\n"
            f"  → разовый, очки мастерства\n\n"
            f"<b>Типы наград:</b>\n{types_str}",
            reply_markup=back_kb("admin_promos"),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_promo_create)
async def msg_promo_create(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    await state.clear()
    raw = message.text.strip().split()

    if len(raw) < 4:
        await message.answer(
            "❌ Неверный формат.\n"
            "Пример: <code>PROMO uses 50 coins:100000 tickets:5</code>",
            parse_mode="HTML",
            reply_markup=back_kb("admin_promos"),
        )
        return

    code = raw[0]
    limit_type = raw[1].lower()
    if limit_type not in ("uses", "time"):
        await message.answer(
            "❌ Второй параметр должен быть <code>uses</code> или <code>time</code>",
            parse_mode="HTML",
            reply_markup=back_kb("admin_promos"),
        )
        return

    try:
        limit_value = int(raw[2])
    except ValueError:
        await message.answer("❌ Третий параметр (кол-во/часы) должен быть числом")
        return

    rewards = []
    for token in raw[3:]:
        if ":" not in token:
            await message.answer(
                f"❌ Формат награды: <code>тип:количество</code>\nПример: <code>coins:100000</code>",
                parse_mode="HTML",
            )
            return
        rtype, ramt_str = token.split(":", 1)
        if rtype not in REWARD_LABELS:
            await message.answer(f"❌ Неизвестный тип: {rtype}")
            return
        try:
            ramt = int(ramt_str)
        except ValueError:
            await message.answer(f"❌ Неверное количество для {rtype}")
            return
        rewards.append({"type": rtype, "amount": ramt})

    from datetime import timedelta
    expires_at = None
    max_uses = 1
    if limit_type == "uses":
        max_uses = limit_value
    else:
        from datetime import datetime, timezone
        expires_at = datetime.now(timezone.utc) + timedelta(hours=limit_value)

    result = await promo_service.create_promo(
        session, code, rewards,
        limit_type=limit_type,
        max_uses=max_uses,
        expires_at=expires_at,
    )
    if result["ok"]:
        summary = _rewards_summary(rewards)
        limit_str = (
            f"Макс. использований: {max_uses}"
            if limit_type == "uses"
            else f"Активен до: {expires_at.strftime('%d.%m.%Y %H:%M UTC')}"
        )
        await message.answer(
            f"✅ <b>Промокод создан!</b>\n\n"
            f"Код: <code>{code.upper()}</code>\n"
            f"Тип: {'по кол-ву' if limit_type == 'uses' else 'по времени'}\n"
            f"{limit_str}\n\n"
            f"🎁 Награды:\n{summary}",
            reply_markup=back_kb("admin_promos"),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"❌ {result['reason']}",
            reply_markup=back_kb("admin_promos"),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("admin_promo_info:"))
async def cb_admin_promo_info(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    promo_id = int(cb.data.split(":")[1])
    from app.models.promo import PromoCode
    promo = await session.scalar(
        select(PromoCode).where(PromoCode.id == promo_id)
    )
    if not promo:
        await cb.answer("Промокод не найден", show_alert=True)
        return

    rewards = _parse_rewards(promo)
    summary = _rewards_summary(rewards)

    builder = InlineKeyboardBuilder()
    if promo.is_active:
        builder.row(InlineKeyboardButton(
            text="❌ Деактивировать",
            callback_data=f"admin_promo_deactivate:{promo_id}"
        ))
    builder.row(InlineKeyboardButton(
        text="🗑 Удалить",
        callback_data=f"admin_promo_delete:{promo_id}"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_promos"))

    if promo.limit_type == "time":
        limit_str = (
            f"До: {promo.expires_at.strftime('%d.%m.%Y %H:%M UTC')}"
            if promo.expires_at else "Без срока"
        )
    else:
        limit_str = f"Использований: {promo.used_count}/{promo.max_uses}"

    try:
        await cb.message.edit_text(
            f"🎁 <b>Промокод {promo.code}</b>\n\n"
            f"Тип: {'⏰ По времени' if promo.limit_type == 'time' else '🔢 По кол-ву'}\n"
            f"{limit_str}\n"
            f"Статус: {'✅ Активен' if promo.is_active else '❌ Неактивен'}\n\n"
            f"🎁 Награды:\n{summary}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("admin_promo_deactivate:"))
async def cb_admin_promo_deactivate(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    promo_id = int(cb.data.split(":")[1])
    result = await promo_service.deactivate_promo(session, promo_id)
    if result["ok"]:
        await cb.answer("✅ Промокод деактивирован")
    else:
        await cb.answer(result["reason"], show_alert=True)
    await cb_admin_promos(cb, session, user)


@router.callback_query(F.data.startswith("admin_promo_delete:"))
async def cb_admin_promo_delete(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    promo_id = int(cb.data.split(":")[1])
    result = await promo_service.delete_promo(session, promo_id)
    if result["ok"]:
        await cb.answer("🗑 Промокод удалён")
    else:
        await cb.answer(result["reason"], show_alert=True)
    await cb_admin_promos(cb, session, user)
