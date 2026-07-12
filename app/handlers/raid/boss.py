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
from app.utils.formatters import fmt_num, progress_bar
from app.constants.raid import (
    BOSS_TIER_HP_MULT,
    BOSS_TIER_UNLOCK_COST,
    BOSS_TIER_NAMES,
    BOSS_TIER_EMOJIS,
    BOSS_TIER_DEFAULT,
)

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
    path = RAID_IMAGE_MAP.get(boss_id)
    if path and Path(path).exists():
        return FSInputFile(path)
    return None


async def _send_or_edit_raid_photo(cb: CallbackQuery, photo, text: str, keyboard) -> None:
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


def _build_boss_text_and_kb(
    clan_id: str, boss: dict, user: User, power: int,
    source_name: str, selected_tier: int,
) -> tuple[str, object]:
    """Строит текст и клавиатуру карточки босса с выбором тира."""
    effective_hp = raid_service.get_effective_boss_hp(boss, selected_tier)
    unlocked = raid_service.get_unlocked_tiers(user)

    reward_type = boss.get("reward_fragments")
    if reward_type == "alchemy":
        reward_line = "🧪 Награда: фрагменты алхимии"
    elif reward_type == "path":
        reward_line = "🔷 Награда: фрагменты Пути"
    elif reward_type == "business":
        reward_line = "🏢 Награда: бизнес-фрагменты"
    else:
        reward_line = "🔮 Награда: фрагменты УИ"

    tier_name = BOSS_TIER_NAMES[selected_tier]
    tier_emoji = BOSS_TIER_EMOJIS[selected_tier]

    text = (
        f"{boss['emoji']} <b>{boss['name']}</b>\n\n"
        f"📖 {boss['description']}\n\n"
        f"💪 Ваша мощь ({source_name}): <b>{fmt_num(power)}</b>\n"
        f"🎯 HP босса: <b>{fmt_num(effective_hp)}</b>  "
        f"[{tier_emoji} Уровень {selected_tier}: {tier_name}]\n"
        f"⏱ Длительность рейда: 1 час\n"
        f"⏳ КД после рейда: {boss['cd_hours']} часов\n"
        f"{reward_line}\n\n"
        f"<b>Выбери уровень сложности:</b>"
    )

    builder = InlineKeyboardBuilder()

    # Кнопки тиров (2 в ряд)
    tier_btns = []
    for t in range(1, 6):
        cost = BOSS_TIER_UNLOCK_COST[t]
        t_emoji = BOSS_TIER_EMOJIS[t]
        t_name = BOSS_TIER_NAMES[t]
        if t in unlocked:
            marker = " ✅" if t == selected_tier else ""
            label = f"{t_emoji} {t_name}{marker}"
        else:
            label = f"🔒 {t_name} ({cost}⚔️)"
        tier_btns.append(InlineKeyboardButton(
            text=label,
            callback_data=f"raid_boss_tier:{clan_id}:{boss['id']}:{t}"
        ))

    # Раскладываем по 2-3 в ряд
    for i in range(0, len(tier_btns), 3):
        builder.row(*tier_btns[i:i+3])

    if selected_tier in unlocked:
        builder.row(InlineKeyboardButton(
            text=f"⚔️ Начать рейд (Уровень {selected_tier})",
            callback_data=f"raid_start:{clan_id}:{boss['id']}:{selected_tier}"
        ))

    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data=f"raid_clan:{clan_id}"
    ))
    return text, builder.as_markup()


# ── Информация о боссе (тир по умолчанию) ────────────────────────────────────

@router.callback_query(F.data.startswith("raid_boss:"))
async def cb_raid_boss(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    clan_id, boss_id = parts[1], parts[2]
    boss = raid_service.get_boss(clan_id, boss_id)
    if not boss:
        await cb.answer("Босс не найден", show_alert=True)
        return

    unlocked = raid_service.get_unlocked_tiers(user)
    if not unlocked:
        await cb.answer(
            "🔒 Сначала разблокируй Уровень 1 в разделе Крафт → Уровни боссов!\n"
            f"Стоимость: {BOSS_TIER_UNLOCK_COST[1]} очков войны",
            show_alert=True,
        )
        return

    # Показываем карточку с наивысшим разблокированным тиром по умолчанию
    default_tier = max(unlocked)
    divisor = boss.get("combat_power_divisor", 2)
    power = await raid_service.get_user_power_for_boss(session, user, boss["damage_source"], divisor)
    if boss["damage_source"] == "squad":
        source_name = "статистов"
    elif boss["damage_source"] == "combat_power":
        source_name = f"боевой мощи (÷{divisor})"
    else:
        source_name = "уникальных персонажей"

    text, kb = _build_boss_text_and_kb(clan_id, boss, user, power, source_name, default_tier)
    photo = _raid_boss_photo(boss_id)
    await _send_or_edit_raid_photo(cb, photo, text, kb)


# ── Выбор тира ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("raid_boss_tier:"))
async def cb_raid_boss_tier(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    clan_id, boss_id, tier_str = parts[1], parts[2], parts[3]
    try:
        tier = int(tier_str)
    except ValueError:
        await cb.answer()
        return

    boss = raid_service.get_boss(clan_id, boss_id)
    if not boss:
        await cb.answer("Босс не найден", show_alert=True)
        return

    # Если тир не разблокирован — показать подсказку
    if not raid_service.is_tier_unlocked(user, tier):
        cost = BOSS_TIER_UNLOCK_COST.get(tier, 0)
        war_pts = getattr(user, "war_points", 0) or 0
        prev_locked = tier > 1 and not raid_service.is_tier_unlocked(user, tier - 1)
        if prev_locked:
            await cb.answer(
                f"🔒 Сначала разблокируй Уровень {tier - 1}!",
                show_alert=True,
            )
        else:
            await cb.answer(
                f"🔒 Уровень {tier} заблокирован\n"
                f"Стоимость: {cost} очков войны\n"
                f"У вас: {war_pts} очков войны\n\n"
                f"Разблокируй в разделе Крафт → Уровни боссов",
                show_alert=True,
            )
        return

    divisor = boss.get("combat_power_divisor", 2)
    power = await raid_service.get_user_power_for_boss(session, user, boss["damage_source"], divisor)
    if boss["damage_source"] == "squad":
        source_name = "статистов"
    elif boss["damage_source"] == "combat_power":
        source_name = f"боевой мощи (÷{divisor})"
    else:
        source_name = "уникальных персонажей"

    text, kb = _build_boss_text_and_kb(clan_id, boss, user, power, source_name, tier)
    photo = _raid_boss_photo(boss_id)
    await _send_or_edit_raid_photo(cb, photo, text, kb)


# ── Старт рейда ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("raid_start:"))
async def cb_raid_start(cb: CallbackQuery, session: AsyncSession, user: User):
    lock_key = cooldown_service.raid_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("Подожди...", show_alert=False)
        return

    parts = cb.data.split(":")
    clan_id, boss_id = parts[1], parts[2]
    tier = int(parts[3]) if len(parts) > 3 else BOSS_TIER_DEFAULT

    result = await raid_service.start_raid(session, user, clan_id, boss_id, tier=tier)
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

    tier_label = f"Уровень {tier}: {BOSS_TIER_NAMES[tier]}"

    # Круговой донат «Корейский дьявол»: мгновенный рейд
    if result.get("instant"):
        doubled_line = "\n🌀 <b>Удача! Награда удвоена!</b>" if result.get("doubled") else ""
        instant_text = (
            f"⚡ <b>Мгновенный рейд!</b>\n\n"
            f"👹 Босс: {result['boss_name']}  [{tier_label}]\n"
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
        f"👹 Босс: {result['boss_name']}  [{tier_label}]\n"
        f"💥 Нанесённый урон: <b>{fmt_num(result['damage'])}</b>\n\n"
        f"⏱ Рейд завершится через: <b>{result['duration_hours']} час</b>\n"
        f"🕐 Время окончания: {ends_at.strftime('%H:%M')}\n\n"
        f"По истечении времени вернись сюда\n"
        f"{frag_line}"
    )
    await _send_or_edit_raid_photo(cb, None, start_text, back_kb("raid_menu"))


# ── Разблокировка тира боссов ─────────────────────────────────────────────────

@router.callback_query(F.data == "craft_boss_tier_menu")
async def cb_craft_boss_tier_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    unlocked = raid_service.get_unlocked_tiers(user)
    war_pts = getattr(user, "war_points", 0) or 0

    lines = []
    for t in range(1, 6):
        cost = BOSS_TIER_UNLOCK_COST[t]
        t_emoji = BOSS_TIER_EMOJIS[t]
        t_name = BOSS_TIER_NAMES[t]
        hp_mult = BOSS_TIER_HP_MULT[t]
        prev_ok = t == 1 or (t - 1) in unlocked
        if t in unlocked:
            lines.append(f"{t_emoji} Ур.{t}: {t_name} (HP ×{hp_mult}) ✅")
        elif not prev_ok:
            lines.append(f"{t_emoji} Ур.{t}: {t_name} (HP ×{hp_mult}) — 🔒 ур.{t - 1}")
        else:
            lines.append(f"{t_emoji} Ур.{t}: {t_name} (HP ×{hp_mult}) — {cost}⚔️")

    text = (
        f"⚔️ <b>Уровни рейд-боссов</b>\n\n"
        f"Очков войны: <b>{war_pts}</b>\n"
        f"Открыто {progress_bar(len(unlocked), 5)} {len(unlocked)}/5\n\n"
        f"━━━ 🎯 Уровни ━━━\n"
        + "\n".join(lines) + "\n\n"
        f"<i>Выбери уровень для разблокировки:</i>"
    )

    builder = InlineKeyboardBuilder()
    for t in range(1, 6):
        cost = BOSS_TIER_UNLOCK_COST[t]
        t_name = BOSS_TIER_NAMES[t]
        prev_ok = t == 1 or (t - 1) in unlocked
        if t in unlocked:
            builder.row(InlineKeyboardButton(
                text=f"✅ Уровень {t}: {t_name}",
                callback_data="noop_raid"
            ))
        elif not prev_ok:
            builder.row(InlineKeyboardButton(
                text=f"🔒 Уровень {t}: {t_name} (сначала уровень {t - 1})",
                callback_data="noop_raid"
            ))
        else:
            can = "✓" if war_pts >= cost else "✗"
            builder.row(InlineKeyboardButton(
                text=f"Уровень {t}: {t_name} — {cost}⚔️ [{can}]",
                callback_data=f"boss_tier_unlock:{t}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="raid_craft"))

    await _send_or_edit_raid_photo(cb, None, text, builder.as_markup())


@router.callback_query(F.data.startswith("boss_tier_unlock:"))
async def cb_boss_tier_unlock(cb: CallbackQuery, session: AsyncSession, user: User):
    try:
        tier = int(cb.data.split(":")[1])
    except (IndexError, ValueError):
        await cb.answer()
        return

    result = await raid_service.unlock_tier(session, user, tier)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    await cb.answer(
        f"✅ Уровень {tier} разблокирован!\n"
        f"Потрачено: {result['cost']} очков войны\n"
        f"Осталось: {result['war_points']}",
        show_alert=True,
    )
    # Обновляем меню
    await cb_craft_boss_tier_menu(cb, session, user)
