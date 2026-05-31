from pathlib import Path

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, FSInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.raid_service import raid_service
from app.services.cooldown_service import cooldown_service
from app.services.quest_service import quest_service
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num

router = Router()

# ── Изображения рейд-боссов ───────────────────────────────────────────────────

RAID_IMAGE_MAP: dict[str, str] = {
    "gun":     "images/raid/gun.png",
    "shingen": "images/raid/shingen.png",
    "jinnen":  "images/raid/jinnen.png",
    "gauren":  "images/raid/gauren.png",
    "elite":   "images/raid/elite.png",
}


def _raid_boss_photo(boss_id: str) -> FSInputFile | None:
    """Возвращает FSInputFile для изображения рейд-босса или None."""
    path = RAID_IMAGE_MAP.get(boss_id)
    if path and Path(path).exists():
        return FSInputFile(path)
    return None


async def _send_or_edit_raid_photo(cb: CallbackQuery, photo, text: str, keyboard) -> None:
    """
    Обновляет сообщение с изображением босса:
    - Если текущее сообщение уже фото → edit_media (обновление на месте).
    - Иначе → удаляем старое и отправляем новое фото.
    - Если картинки нет → пробуем edit_text, при ошибке — delete + answer.
    """
    if photo:
        if cb.message.photo:
            try:
                await cb.message.edit_media(
                    InputMediaPhoto(media=photo, caption=text, parse_mode="HTML"),
                    reply_markup=keyboard,
                )
                return
            except Exception:
                pass
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer_photo(photo, caption=text, reply_markup=keyboard, parse_mode="HTML")
    else:
        try:
            await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            try:
                await cb.message.delete()
            except Exception:
                pass
            await cb.message.answer(text, reply_markup=keyboard, parse_mode="HTML")


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
    elif reward_type == "business":
        reward_line = "🏢 Награда: бизнес-фрагменты (макс 15)"
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

    boss_id_key = boss.get("id", "")
    photo = _raid_boss_photo(boss_id_key)
    text = (
        f"{boss['emoji']} <b>{boss['name']}</b>\n\n"
        f"📖 {boss['description']}\n\n"
        f"💪 Ваша мощь ({source_name}): <b>{fmt_num(power)}</b>\n"
        f"🎯 HP босса: {fmt_num(boss['base_hp'])}\n"
        f"⏱ Длительность рейда: 1 час\n"
        f"⏳ КД после рейда: {boss['cd_hours']} часов\n"
        f"{reward_line}\n\n"
        f"После начала рейда у тебя есть 1 час\n"
        f"чтобы нанести максимум урона!"
    )
    await _send_or_edit_raid_photo(cb, photo, text, builder.as_markup())


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

    await quest_service.add_progress(session, user, "raid_start")

    reward_type = result.get("reward_type", "ui")
    if reward_type == "alchemy":
        frag_emoji, frag_name = "🧪", "фрагменты алхимии"
    elif reward_type == "path":
        frag_emoji, frag_name = "🔷", "фрагменты Пути"
    elif reward_type == "business":
        frag_emoji, frag_name = "🏢", "бизнес-фрагменты"
    else:
        frag_emoji, frag_name = "🔮", "фрагменты УИ"

    # Круговой донат «Корейский дьявол»: мгновенный рейд
    if result.get("instant"):
        doubled_line = "\n🌀 <b>Удача! Награда удвоена!</b>" if result.get("doubled") else ""
        instant_text = (
            f"⚡ <b>Мгновенный рейд!</b>\n\n"
            f"👹 Босс: {result['boss_name']}\n"
            f"💥 Нанесённый урон: <b>{fmt_num(result['damage'])}</b>\n\n"
            f"{frag_emoji} Получено {frag_name}: <b>+{result['fragments']}</b>\n"
            f"📊 Всего: <b>{result['total_fragments']}</b>"
            + doubled_line
        )
        await _send_or_edit_raid_photo(cb, None, instant_text, back_kb("raid_menu"))
        return

    ends_at = result["ends_at"]
    if reward_type == "alchemy":
        frag_line = "чтобы получить фрагменты алхимии!"
    elif reward_type == "path":
        frag_line = "чтобы получить фрагменты Пути!"
    elif reward_type == "business":
        frag_line = "чтобы получить бизнес-фрагменты!"
    else:
        frag_line = "чтобы получить фрагменты УИ!"
    start_text = (
        f"⚔️ <b>Рейд начался!</b>\n\n"
        f"👹 Босс: {result['boss_name']}\n"
        f"💥 Нанесённый урон: <b>{fmt_num(result['damage'])}</b>\n\n"
        f"⏱ Рейд завершится через: <b>{result['duration_hours']} час</b>\n"
        f"🕐 Время окончания: {ends_at.strftime('%H:%M')}\n\n"
        f"По истечении времени вернись сюда\n"
        f"{frag_line}"
    )
    await _send_or_edit_raid_photo(cb, None, start_text, back_kb("raid_menu"))
