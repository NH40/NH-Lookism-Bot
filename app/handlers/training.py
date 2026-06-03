from pathlib import Path

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, FSInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.skill import UserMastery
from app.services.training_service import training_service
from app.services.cooldown_service import cooldown_service
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num
from app.constants.training import TRAINERS, WAR_GENIUS_LEVEL_COSTS, WAR_GENIUS_BOSS_LABELS

router = Router()


# ── Меню тренировки (список тренеров) ────────────────────────────────────────

@router.callback_query(F.data == "training_menu")
async def cb_training_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.bank.credits_service import credits_service
    block_msg = await credits_service.block_message(session, user.id)
    if block_msg:
        try:
            await cb.message.edit_text(block_msg, reply_markup=back_kb("bank_credits"), parse_mode="HTML")
        except Exception:
            pass
        await cb.answer()
        return

    trainers_info = await training_service.get_trainers_info(user.id)

    builder = InlineKeyboardBuilder()
    for t in trainers_info:
        if t["on_cd"]:
            ttl_str = cooldown_service.format_ttl(t["ttl"])
            builder.row(InlineKeyboardButton(
                text=f"{t['emoji']} {t['name']} — ⏳ {ttl_str}",
                callback_data=f"trainer_info:{t['id']}"
            ))
        else:
            builder.row(InlineKeyboardButton(
                text=f"{t['emoji']} {t['name']}",
                callback_data=f"trainer_info:{t['id']}"
            ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))

    r = await session.execute(select(UserMastery).where(UserMastery.user_id == user.id))
    mastery = r.scalar_one_or_none()

    from app.data.skills import MASTERY
    bonus_map = {0: 0, 1: 5, 2: 10, 3: 20, 4: 30}
    speed_map = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
    mastery_lines = []
    for m in MASTERY:
        current = getattr(mastery, m.skill_id, 0) if mastery else 0
        if m.skill_id in ("strength", "technique"):
            bonus = bonus_map.get(current, 0)
        else:
            bonus = speed_map.get(current, 0)
        mastery_lines.append(f"  {m.emoji} {m.name}: {current}/4 (+{bonus}%)")

    war_points = getattr(user, "war_points", 0)
    war_genius = getattr(user, "war_genius_level", 0)
    war_str = f"⚔️ Очки войны: <b>{war_points}</b> | Гений войны: <b>{war_genius}/5</b>"

    text = (
        f"🏋 <b>Тренировка</b>\n\n"
        f"⭐ Очки мастерства: <b>{user.mastery_points}</b>\n"
        f"🔷 Очки пути: <b>{user.skill_path_points}</b>\n"
        f"{war_str}\n\n"
        f"<b>Текущее мастерство:</b>\n"
        + "\n".join(mastery_lines)
        + "\n\n"
        f"Нажми на тренера, чтобы узнать подробности:"
    )

    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


# ── Карточка тренера (с фото) ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("trainer_info:"))
async def cb_trainer_info(cb: CallbackQuery, session: AsyncSession, user: User):
    trainer_id = cb.data.split(":")[1]
    trainer = next((t for t in TRAINERS if t["id"] == trainer_id), None)
    if not trainer:
        await cb.answer("Тренер не найден", show_alert=True)
        return

    cd_key = training_service.trainer_cd_key(user.id, trainer_id)
    on_cd = await cooldown_service.is_on_cooldown(cd_key)
    ttl = await cooldown_service.get_ttl(cd_key) if on_cd else 0

    # Скидка Императора применяется к Тому Ли и Чон Гону
    base_cost = trainer['cost']
    if trainer_id in ('tom_lee', 'jeon_gon'):
        discount = getattr(user, 'circ_trainer_discount', 0)
        effective_cost = max(1, int(base_cost * (1 - discount / 100)))
    else:
        discount = 0
        effective_cost = base_cost

    builder = InlineKeyboardBuilder()
    if on_cd:
        builder.row(InlineKeyboardButton(
            text=f"⏳ Тренироваться — КД {cooldown_service.format_ttl(ttl)}",
            callback_data="noop_training"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text=f"💪 Тренироваться ({fmt_num(effective_cost)} NHCoin)",
            callback_data=f"train_with:{trainer_id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="trainer_back"))

    war_extra = ""
    if trainer_id == "manager_kim":
        war_points = getattr(user, "war_points", 0)
        war_genius = getattr(user, "war_genius_level", 0)
        war_extra = (
            f"\n\n⚔️ Очков войны: <b>{war_points}</b>\n"
            f"🎖 Гений войны: <b>{war_genius}/5</b>"
        )
        if war_genius < 5:
            next_cost = WAR_GENIUS_LEVEL_COSTS[war_genius]
            boss_lbl = WAR_GENIUS_BOSS_LABELS.get(war_genius + 1, "")
            war_extra += f"\nСледующий ур. ({war_genius + 1}): <b>{next_cost}</b> очков → {boss_lbl}"

    cost_line = f"💰 Цена: <b>{fmt_num(effective_cost)} NHCoin</b>"
    if discount:
        cost_line += f" <i>(-{discount}% скидка)</i>"

    caption = (
        f"{trainer['emoji']} <b>{trainer['name']}</b>\n\n"
        f"{trainer['description']}\n\n"
        f"{cost_line}\n"
        f"⏳ КД: <b>{trainer['cd'] // 3600} ч</b>\n"
        f"🎁 Награда: <b>{trainer['reward']}</b>"
        + war_extra
    )

    photo_path = trainer.get("photo")
    if photo_path and Path(photo_path).exists():
        photo = FSInputFile(photo_path)
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer_photo(
            photo, caption=caption, reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    else:
        try:
            await cb.message.edit_text(caption, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            try:
                await cb.message.delete()
            except Exception:
                pass
            await cb.message.answer(caption, reply_markup=builder.as_markup(), parse_mode="HTML")

    await cb.answer()


# ── Кнопка «Назад» из карточки тренера ───────────────────────────────────────

@router.callback_query(F.data == "trainer_back")
async def cb_trainer_back(cb: CallbackQuery, session: AsyncSession, user: User):
    try:
        await cb.message.delete()
    except Exception:
        pass
    # После удаления фото-сообщения отправляем новое текстовое сообщение
    # cb_training_menu сам справится с edit_text или answer
    await cb_training_menu(cb, session, user)
    await cb.answer()


# ── Выполнить тренировку ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("train_with:"))
async def cb_train_with(cb: CallbackQuery, session: AsyncSession, user: User):
    trainer_id = cb.data.split(":")[1]

    lock_key = cooldown_service.train_lock_key(user.id, trainer_id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("Подожди...", show_alert=False)
        return

    if trainer_id == "tom_lee":
        result = await training_service.train_with_tom(session, user)
        if not result["ok"]:
            await cb.answer(result["reason"], show_alert=True)
            return
        from app.services.quest_service import quest_service
        await quest_service.add_progress(session, user, "train")
        points = result["points"]
        result_text = (
            f"🥋 <b>Тренировка с Томом Ли завершена!</b>\n\n"
            f"💸 Потрачено: {fmt_num(result['cost'])} NHCoin\n"
            f"⭐ Получено очков мастерства: <b>+{points}</b>\n"
            f"📊 Всего очков мастерства: <b>{result['total_points']}</b>\n\n"
            f"⏳ КД: 2 часа\n\n"
            f"Прокачай мастерство в <b>Навыки → Мастерство</b>"
        )

    elif trainer_id == "jeon_gon":
        result = await training_service.train_with_jeon_gon(session, user)
        if not result["ok"]:
            await cb.answer(result["reason"], show_alert=True)
            return
        from app.services.quest_service import quest_service
        await quest_service.add_progress(session, user, "train")
        points = result["points"]
        path_emoji = {"businessman": "💼", "romantic": "💝", "monster": "👹"}.get(user.skill_path, "🛤")
        result_text = (
            f"🧘 <b>Тренировка с Чон Гоном завершена!</b>\n\n"
            f"💸 Потрачено: {fmt_num(result['cost'])} NHCoin\n"
            f"🔷 Получено очков пути: <b>+{points}</b>\n"
            f"📊 Всего очков пути: <b>{result['total_points']}</b>\n"
            f"{path_emoji} Путь: {user.skill_path}\n\n"
            f"⏳ КД: 2 часа\n\n"
            f"Прокачай навыки пути в <b>Навыки → Путь</b>"
        )

    elif trainer_id == "manager_kim":
        result = await training_service.train_with_manager_kim(session, user)
        if not result["ok"]:
            await cb.answer(result["reason"], show_alert=True)
            return
        from app.services.quest_service import quest_service
        await quest_service.add_progress(session, user, "train")
        points = result["points"]
        war_genius = getattr(user, "war_genius_level", 0)
        result_text = (
            f"💼 <b>Тренировка с Менеджером Кимом завершена!</b>\n\n"
            f"💸 Потрачено: {fmt_num(result['cost'])} NHCoin\n"
            f"⚔️ Получено очков войны: <b>+{points}</b>\n"
            f"📊 Всего очков войны: <b>{result['total_points']}</b>\n"
            f"🎖 Гений войны: <b>{war_genius}/5</b>\n\n"
            f"⏳ КД: 2 часа\n\n"
            f"Прокачай Гений войны в <b>Навыки → Гений войны</b>"
        )

    else:
        await cb.answer("Тренер не найден", show_alert=True)
        return

    # Показываем результат: если текущее сообщение — фото, удаляем и отправляем текст
    try:
        if cb.message.photo:
            await cb.message.delete()
            await cb.message.answer(result_text, reply_markup=back_kb("training_menu"), parse_mode="HTML")
        else:
            await cb.message.edit_text(result_text, reply_markup=back_kb("training_menu"), parse_mode="HTML")
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(result_text, reply_markup=back_kb("training_menu"), parse_mode="HTML")


@router.callback_query(F.data == "noop_training")
async def cb_noop_training(cb: CallbackQuery):
    await cb.answer()
