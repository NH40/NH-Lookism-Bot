from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.raid_service import raid_service
from app.services.cooldown_service import cooldown_service
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num

router = Router()


# ── Информация о боссе ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("raid_boss:"))
async def cb_raid_boss(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    clan_id, boss_id = parts[1], parts[2]
    boss = raid_service.get_boss(clan_id, boss_id)
    if not boss:
        await cb.answer("Босс не найден", show_alert=True)
        return

    divisor = boss.get("combat_power_divisor", 2)
    power = await raid_service.get_user_power_for_boss(session, user, boss["damage_source"], divisor)
    if boss["damage_source"] == "squad":
        source_name = "статистов"
    elif boss["damage_source"] == "combat_power":
        source_name = f"боевой мощи (÷{divisor})"
    else:
        source_name = "уникальных персонажей"

    reward_type = boss.get("reward_fragments")
    if reward_type == "alchemy":
        reward_line = "🧪 Награда: фрагменты алхимии (макс 25)"
    elif reward_type == "path":
        reward_line = "🔷 Награда: фрагменты Пути (макс 20)"
    else:
        reward_line = "🔮 Награда: фрагменты УИ"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"⚔️ Начать рейд",
        callback_data=f"raid_start:{clan_id}:{boss_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data=f"raid_clan:{clan_id}"
    ))

    await cb.message.edit_text(
        f"{boss['emoji']} <b>{boss['name']}</b>\n\n"
        f"📖 {boss['description']}\n\n"
        f"💪 Ваша мощь ({source_name}): <b>{fmt_num(power)}</b>\n"
        f"🎯 HP босса: {fmt_num(boss['base_hp'])}\n"
        f"⏱ Длительность рейда: 1 час\n"
        f"⏳ КД после рейда: {boss['cd_hours']} часов\n"
        f"{reward_line}\n\n"
        f"После начала рейда у тебя есть 1 час\n"
        f"чтобы нанести максимум урона!",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


# ── Старт рейда ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("raid_start:"))
async def cb_raid_start(cb: CallbackQuery, session: AsyncSession, user: User):
    lock_key = cooldown_service.raid_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("Подожди...", show_alert=False)
        return

    parts = cb.data.split(":")
    clan_id, boss_id = parts[1], parts[2]

    result = await raid_service.start_raid(session, user, clan_id, boss_id)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    ends_at = result["ends_at"]
    reward_type = result.get("reward_type", "ui")
    if reward_type == "alchemy":
        frag_line = "чтобы получить фрагменты алхимии!"
    elif reward_type == "path":
        frag_line = "чтобы получить фрагменты Пути!"
    else:
        frag_line = "чтобы получить фрагменты УИ!"
    await cb.message.edit_text(
        f"⚔️ <b>Рейд начался!</b>\n\n"
        f"👹 Босс: {result['boss_name']}\n"
        f"💥 Нанесённый урон: <b>{fmt_num(result['damage'])}</b>\n\n"
        f"⏱ Рейд завершится через: <b>{result['duration_hours']} час</b>\n"
        f"🕐 Время окончания: {ends_at.strftime('%H:%M')}\n\n"
        f"По истечении времени вернись сюда\n"
        f"{frag_line}",
        reply_markup=back_kb("raid_menu"),
        parse_mode="HTML",
    )
