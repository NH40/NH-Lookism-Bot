from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.models.user import User
from app.models.raid import RaidSession
from app.services.raid_service import raid_service
from app.services.cooldown_service import cooldown_service
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num

router = Router()


# ── Статус рейда ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("raid_status:"))
async def cb_raid_status(cb: CallbackQuery, session: AsyncSession, user: User):
    from sqlalchemy import select as sa_select
    raid_id = int(cb.data.split(":")[1])
    result = await session.execute(
        sa_select(RaidSession).where(RaidSession.id == raid_id)
    )
    raid = result.scalar_one_or_none()
    if not raid:
        await cb.answer("Рейд не найден", show_alert=True)
        return

    now = datetime.now(timezone.utc)
    remaining = max(0, int((raid.ends_at - now).total_seconds()))
    boss = raid_service.get_boss(raid.clan_id, raid.boss_id)

    attack_cd = await raid_service.get_attack_cd_info(raid_id, user.id)

    builder = InlineKeyboardBuilder()

    can_attack_now = remaining > 0 and not attack_cd["on_cd"]

    if remaining == 0:
        builder.row(InlineKeyboardButton(
            text="🎁 Получить награду!",
            callback_data=f"raid_claim:{raid_id}"
        ))
    else:
        if can_attack_now:
            builder.row(InlineKeyboardButton(
                text="⚔️ Атаковать босса!",
                callback_data=f"raid_attack:{raid_id}"
            ))
        else:
            ttl_str = cooldown_service.format_ttl(attack_cd["ttl"])
            builder.row(InlineKeyboardButton(
                text=f"⚔️ Атака — ⏳ {ttl_str}",
                callback_data="noop_raid"
            ))

    builder.row(InlineKeyboardButton(
        text="🔄 Обновить", callback_data=f"raid_status:{raid_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="raid_menu"
    ))

    boss_name = boss["name"] if boss else raid.boss_id
    boss_hp = boss["base_hp"] if boss else 0

    damage_pct = min(100.0, (raid.damage_dealt / boss_hp * 100)) if boss_hp > 0 else 0
    hp_bar_filled = int(damage_pct / 10)
    hp_bar = "🟥" * hp_bar_filled + "⬛" * (10 - hp_bar_filled)

    status_line = (
        f"⏳ До конца рейда: {cooldown_service.format_ttl(remaining)}"
        if remaining > 0 else "✅ Рейд завершён! Забери награду."
    )
    extra_line = ""
    if remaining > 0 and not attack_cd["on_cd"]:
        extra_line = "\n\n⚔️ Атакуй снова чтобы накопить больше урона!"

    await cb.message.edit_text(
        f"⚔️ <b>Активный рейд — {boss_name}</b>\n\n"
        f"❤️ HP босса: {fmt_num(boss_hp)}\n"
        f"💥 Нанесённый урон: <b>{fmt_num(raid.damage_dealt)}</b> ({damage_pct:.1f}%)\n"
        f"{hp_bar}\n"
        f"🗡 Атак совершено: <b>{raid.attack_count}</b>\n\n"
        + status_line + extra_line,
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


# ── Атака на босса ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("raid_attack:"))
async def cb_raid_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    raid_id = int(cb.data.split(":")[1])
    result = await raid_service.attack_boss(session, user, raid_id)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    if result.get("boss_killed"):
        rt = result.get("reward_type")
        if rt == "alchemy":
            frag_emoji, frag_name = "🧪", "фрагментов алхимии"
        elif rt == "path":
            frag_emoji, frag_name = "🔷", "фрагментов Пути"
        else:
            frag_emoji, frag_name = "🔮", "фрагментов УИ"
        await cb.answer(
            f"💀 Босс повержен!\n"
            f"{frag_emoji} Получено: +{result['fragments']}",
            show_alert=True
        )
        await cb.message.edit_text(
            f"🎉 <b>Босс {result['boss_name']} повержен!</b>\n\n"
            f"💥 Суммарный урон: <b>{fmt_num(result['total_damage'])}</b>\n"
            f"🗡 Атак совершено: <b>{result['attack_count']}</b>\n\n"
            f"{frag_emoji} Получено {frag_name}: <b>+{result['fragments']}</b>\n"
            f"📊 Всего: <b>{result['total_fragments']}</b>\n\n"
            f"Используй фрагменты в <b>Рейды → Крафт</b>!",
            reply_markup=back_kb("raid_menu"),
            parse_mode="HTML",
        )
    else:
        await cb.answer(
            f"⚔️ +{fmt_num(result['damage'])} урона!\n"
            f"Всего: {fmt_num(result['total_damage'])}",
            show_alert=True
        )
        await cb_raid_status(cb, session, user)
