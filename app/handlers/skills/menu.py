from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.skill import UserMastery
from app.utils.formatters import skill_path_label, progress_bar, pair_lines
from app.constants.training import WAR_GENIUS_LEVEL_COSTS, WAR_GENIUS_BOSS_LABELS

router = Router()


@router.callback_query(F.data == "skills")
async def cb_skills(cb: CallbackQuery, session: AsyncSession, user: User):
    await session.execute(
        select(UserMastery).where(UserMastery.user_id == user.id)
    )

    path_emoji = {
        "businessman": "💼", "romantic": "💝", "monster": "👹", "shadow": "🌑"
    }.get(user.skill_path, "❓") if user.skill_path else "❓"

    ui_status = "✅ Активен" if (user.ultra_instinct or user.true_ultra_instinct or user.ui_is_donat or user.ui_level > 0) else "❌"

    from app.handlers.skills.med_genius import any_unlocked, _unlocked_count, MG_POTIONS, is_donat as _mg_is_donat
    if _mg_is_donat(user):
        mg_status = "Донат (все Ур.6)"
    elif any_unlocked(user):
        mg_status = f"{_unlocked_count(user)}/{len(MG_POTIONS)} зелий"
    else:
        mg_status = "🔒 не открыт"

    war_genius = getattr(user, "war_genius_level", 0)
    war_points = getattr(user, "war_points", 0)
    wg_status = f"Ур.{war_genius}/5" if war_genius > 0 else "🔒 не открыт"
    biz_genius = getattr(user, "business_genius_level", 0)
    bg_status = f"Ур.{biz_genius}/5" if biz_genius > 0 else "🔒 не открыт"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚔️ Мастерство",            callback_data="mastery_menu"))
    builder.row(InlineKeyboardButton(text="🗺 Путь",                   callback_data="path_menu" if user.skill_path else "path_choose"))
    builder.row(InlineKeyboardButton(text="👁 Ультра Инстинкт",        callback_data="ui_settings"))
    builder.row(InlineKeyboardButton(text=f"🩺 Гений медицины ({mg_status})", callback_data="med_genius"))
    builder.row(InlineKeyboardButton(text=f"⚔️ Гений войны ({wg_status})", callback_data="war_genius_menu"))
    builder.row(InlineKeyboardButton(text=f"🎖 Гений бизнеса ({bg_status})", callback_data="biz_genius_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Назад",                  callback_data="main_menu"))

    text = (
        f"⚡ <b>Навыки</b>\n\n"
        f"💎 Очков пути: <b>{user.skill_path_points}</b>   ⚔️ Очков войны: <b>{war_points}</b>\n\n"
        f"━━━ 📊 Статус ━━━\n"
        f"🗺 Путь: {path_emoji} <b>{skill_path_label(user.skill_path)}</b>\n"
        f"👁 Ультра Инстинкт: {ui_status}\n"
        f"🩺 Гений медицины: <b>{mg_status}</b>\n"
        f"⚔️ Гений войны {progress_bar(war_genius, 5)} {war_genius}/5\n"
        f"🎖 Гений бизнеса {progress_bar(biz_genius, 5)} {biz_genius}/5\n\n"
        f"Выбери раздел:"
    )
    if cb.message.photo:
        # Раздел «Путь» отправляет фото (caption), а не текст — edit_text на таком
        # сообщении падает с "there is no text in the message to edit".
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "war_genius_menu")
async def cb_war_genius_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    war_points = getattr(user, "war_points", 0)
    war_genius = getattr(user, "war_genius_level", 0)

    builder = InlineKeyboardBuilder()

    if war_genius < 5:
        next_cost = WAR_GENIUS_LEVEL_COSTS[war_genius]
        can = "✅" if war_points >= next_cost else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can} Прокачать до Ур.{war_genius + 1} — {next_cost} ⚔️",
            callback_data=f"war_genius_buy:{war_genius + 1}"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="✅ Гений войны — МАКСИМУМ (5/5)",
            callback_data="noop"
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="skills"))

    lines = [
        "🎖 <b>Гений войны</b>",
        "",
        f"⚔️ Очков войны: <b>{war_points}</b>",
        f"Уровень {progress_bar(war_genius, 5)} <b>{war_genius}/5</b>",
        "",
        "━━━ 📖 Что даёт ━━━",
        "<i>Авто-атака по рейд-боссу по кулдауну.</i>",
        "<i>Запусти рейд вручную — дальше атаки идут сами!</i>",
        "",
        "━━━ 🎯 Уровни ━━━",
    ]

    level_bits = []
    for lvl in range(1, 6):
        cost = WAR_GENIUS_LEVEL_COSTS[lvl - 1]
        boss_lbl = WAR_GENIUS_BOSS_LABELS.get(lvl, "")
        if war_genius >= lvl:
            level_bits.append(f"✅ Ур.{lvl}: {boss_lbl}")
        elif war_genius + 1 == lvl:
            level_bits.append(f"🔓 Ур.{lvl}: {boss_lbl} — {cost}⚔️")
        else:
            level_bits.append(f"🔒 Ур.{lvl}: {boss_lbl} — {cost}⚔️")
    lines.extend(pair_lines(level_bits))

    lines.append("")
    lines.append("<i>Очки войны — у тренера Менеджер Ким</i>")

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("war_genius_buy:"))
async def cb_war_genius_buy(cb: CallbackQuery, session: AsyncSession, user: User):
    target = int(cb.data.split(":")[1])
    war_genius = getattr(user, "war_genius_level", 0)
    war_points = getattr(user, "war_points", 0)

    if target != war_genius + 1:
        await cb.answer("Прокачивай уровни по порядку!", show_alert=True)
        return
    if target > 5:
        await cb.answer("Максимальный уровень достигнут!", show_alert=True)
        return

    cost = WAR_GENIUS_LEVEL_COSTS[war_genius]
    if war_points < cost:
        await cb.answer(f"Нужно {cost} ⚔️ очков войны", show_alert=True)
        return

    user.war_points = war_points - cost
    user.war_genius_level = target
    await session.flush()

    boss_lbl = WAR_GENIUS_BOSS_LABELS.get(target, "")
    await cb.answer(
        f"✅ Гений войны Ур.{target} открыт!\n"
        f"Авто-рейд на {boss_lbl} активирован!",
        show_alert=True
    )
    await cb_war_genius_menu(cb, session, user)


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()
