import random
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.emperor_gang import EmperorGangRecord
from app.constants.emperor import (
    EMPEROR_GANGS, EMPEROR_GANG_MAP,
    GANG_COOLDOWN_HOURS, GANG_STRENGTH_GROWTH,
)
from app.utils.formatters import fmt_num, fmt_ttl

router = Router()

# Весовые коэффициенты рангов для дропа в контексте императора — константа модуля
_EMPEROR_WEIGHTS = {
    "king":        6.0,
    "strong_king": 5.0,
    "gen_zero":    7.0,
    "new_legend":  4.0,
    "legend":      2.5,
    "peak":        1.5,
    "absolute":    0.8,
    "perfection":  0.3,
}

# ── Вспомогательные ───────────────────────────────────────────────────────────

def _gang_power(cfg, defeat_count: int) -> int:
    """Мощь группировки с учётом роста после каждой победы (+20%)."""
    return int(cfg.base_power * ((1 + GANG_STRENGTH_GROWTH) ** defeat_count))


async def _batch_get_records(
    session: AsyncSession, user_id: int
) -> dict[str, EmperorGangRecord]:
    """Загружает все записи пользователя одним запросом."""
    rows = (await session.execute(
        select(EmperorGangRecord).where(EmperorGangRecord.user_id == user_id)
    )).scalars().all()
    return {r.gang_id: r for r in rows}


async def _compute_speed_pct(session: AsyncSession, user: User) -> int:
    """Вычисляет % снижения КД с учётом мастерства и титулов. 2 запроса вместо 4."""
    from app.models.skill import UserMastery
    from app.repositories.title_repo import title_repo

    speed = await session.scalar(
        select(UserMastery.speed).where(UserMastery.user_id == user.id)
    )
    speed_level = 4 if getattr(user, "fame_charles_invisible", False) else min(
        4, (speed or 0) + getattr(user, "clan_land_speed_mastery_bonus", 0)
    )
    raw = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}.get(speed_level, 0)
    speed_pct = int(raw * getattr(user, "skill_path_bonus_multiplier", 1.0))

    title_ids = set(await title_repo.get_user_titles(session, user.id))
    if {"concentration", "focus"}.issubset(title_ids):
        speed_pct = min(80, speed_pct + 15)
    if "reverse_eyes" in title_ids:
        speed_pct = min(80, speed_pct + 30)
    if "concentration" in title_ids:
        speed_pct = min(80, speed_pct + 30)
    return speed_pct


async def _build_gang_list(session: AsyncSession, user: User) -> tuple[str, any]:
    now = datetime.now(timezone.utc)
    builder = InlineKeyboardBuilder()

    # Один запрос вместо N (по одному на каждую группировку)
    records = await _batch_get_records(session, user.id)

    lines = [f"⚔️ <b>Группировки Императора</b>\n"]

    for cfg in EMPEROR_GANGS:
        rec = records.get(cfg.gang_id)
        defeat_count = rec.defeat_count if rec else 0
        cooldown_until = rec.cooldown_until if rec else None

        power = _gang_power(cfg, defeat_count)
        on_cd = cooldown_until and cooldown_until > now

        if on_cd:
            secs = int((cooldown_until - now).total_seconds())
            status_icon = "🔒"
            btn_text = f"{cfg.emoji} {cfg.name} | ⏳ {fmt_ttl(secs)}"
            cd_data = f"emperor_gang_cd:{cfg.gang_id}"
            builder.row(InlineKeyboardButton(text=btn_text, callback_data=cd_data))
        else:
            can_win = user.combat_power >= power
            can_icon = "✅" if can_win else "❌"
            streak = f" [+{defeat_count * 20}%]" if defeat_count > 0 else ""
            btn_text = f"{cfg.emoji} {cfg.name}{streak} | {fmt_num(power)} | {can_icon}"
            builder.row(InlineKeyboardButton(
                text=btn_text,
                callback_data=f"emperor_gang_info:{cfg.gang_id}"
            ))

    builder.row(InlineKeyboardButton(text="🌟 Пробуждения", callback_data="emperor_awakening"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    text = (
        f"⚔️ <b>Группировки Императора</b>\n\n"
        f"💪 Ваша мощь: <b>{fmt_num(user.combat_power)}</b>\n\n"
        f"Побеждайте группировки — они усиливаются на <b>20%</b> после каждого поражения.\n"
        f"Перезарядка: <b>{GANG_COOLDOWN_HOURS} час</b>"
    )
    return text, builder.as_markup()


# ── Главное меню Emperor ──────────────────────────────────────────────────────

@router.callback_query(F.data == "emperor_gangs")
async def cb_emperor_gangs(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.phase != "emperor":
        await cb.answer("Только для Императора!", show_alert=True)
        return
    text, kb = await _build_gang_list(session, user)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()


# ── Информация о группировке ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("emperor_gang_info:"))
async def cb_emperor_gang_info(cb: CallbackQuery, session: AsyncSession, user: User):
    gang_id = cb.data.split(":")[1]
    cfg = EMPEROR_GANG_MAP.get(gang_id)
    if not cfg:
        await cb.answer("Группировка не найдена", show_alert=True)
        return

    rec = await session.scalar(
        select(EmperorGangRecord).where(
            EmperorGangRecord.user_id == user.id,
            EmperorGangRecord.gang_id == gang_id,
        )
    )
    defeat_count = rec.defeat_count if rec else 0
    power = _gang_power(cfg, defeat_count)
    now = datetime.now(timezone.utc)

    on_cd = rec and rec.cooldown_until and rec.cooldown_until > now
    if on_cd:
        secs = int((rec.cooldown_until - now).total_seconds())
        await cb.answer(f"⏳ Перезарядка: {fmt_ttl(secs)}", show_alert=True)
        return

    can_win = user.combat_power >= power
    can_icon = "✅" if can_win else "⚠️"

    members_str = "\n".join(f"  • {m}" for m in cfg.members)
    growth_str = f" (×{(1 + GANG_STRENGTH_GROWTH) ** defeat_count:.2f} от базы)" if defeat_count > 0 else ""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"⚔️ Атаковать",
        callback_data=f"emperor_gang_attack:{gang_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="emperor_gangs"
    ))

    try:
        await cb.message.edit_text(
            f"{cfg.emoji} <b>{cfg.name}</b>\n\n"
            f"{cfg.desc}\n\n"
            f"👥 Состав:\n{members_str}\n\n"
            f"💪 Мощь: <b>{fmt_num(power)}</b>{growth_str}\n"
            f"🏆 Побед: <b>{defeat_count}</b>\n\n"
            f"🎁 Награда:\n"
            f"  💎 50–150 пыли (5–15 при поражении)\n"
            f"  🃏 Шанс карточки: {cfg.drop_chance}%\n\n"
            f"{can_icon} Ваша мощь: {fmt_num(user.combat_power)} / {fmt_num(power)}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("emperor_gang_cd:"))
async def cb_emperor_gang_cd(cb: CallbackQuery, session: AsyncSession, user: User):
    gang_id = cb.data.split(":")[1]
    rec = await session.scalar(
        select(EmperorGangRecord).where(
            EmperorGangRecord.user_id == user.id,
            EmperorGangRecord.gang_id == gang_id,
        )
    )
    now = datetime.now(timezone.utc)
    if rec and rec.cooldown_until and rec.cooldown_until > now:
        secs = int((rec.cooldown_until - now).total_seconds())
        await cb.answer(f"⏳ Перезарядка: {fmt_ttl(secs)}", show_alert=True)
    else:
        await cb.answer("Можно атаковать!")


# ── Атака ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("emperor_gang_attack:"))
async def cb_emperor_gang_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.phase != "emperor":
        await cb.answer("Только для Императора!", show_alert=True)
        return

    gang_id = cb.data.split(":")[1]
    cfg = EMPEROR_GANG_MAP.get(gang_id)
    if not cfg:
        await cb.answer("Группировка не найдена", show_alert=True)
        return

    from app.services.cooldown_service import cooldown_service

    lock_key = cooldown_service.emperor_attack_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=15):
        await cb.answer("⏳ Атака уже обрабатывается", show_alert=True)
        return

    try:
        now = datetime.now(timezone.utc)

        rec = await session.scalar(
            select(EmperorGangRecord).where(
                EmperorGangRecord.user_id == user.id,
                EmperorGangRecord.gang_id == gang_id,
            )
        )
        if not rec:
            rec = EmperorGangRecord(user_id=user.id, gang_id=gang_id, defeat_count=0)
            session.add(rec)
            await session.flush()

        if rec.cooldown_until and rec.cooldown_until > now:
            secs = int((rec.cooldown_until - now).total_seconds())
            await cb.answer(f"⏳ КД: {fmt_ttl(secs)}", show_alert=True)
            return

        gang_power = _gang_power(cfg, rec.defeat_count)

        from app.services.combat_service import fight_district
        fight = await fight_district(session, user, gang_power)
        won = fight["win"]
        user_power = fight["user_power"]

        if getattr(user, "fame_set_gaprena", False):
            from app.services.fame_service import fame_service
            await fame_service.gain_overcome_stack(user.id)

        result_lines = [f"{cfg.emoji} <b>Бой: {cfg.name}</b>\n"]
        result_lines.append(f"💪 Ваша мощь: {fmt_num(user_power)}")
        result_lines.append(f"👊 Мощь врага: {fmt_num(gang_power)}\n")

        dropped_char: dict | None = None

        # КД считаем один раз для обоих исходов (2 запроса вместо 4)
        speed_pct = await _compute_speed_pct(session, user)
        base_cd_seconds = GANG_COOLDOWN_HOURS * 3600
        effective_cd = max(600, int(base_cd_seconds * (1 - speed_pct / 100)))

        if won:
            dust_reward = random.randint(50, 150)
            user.card_dust += dust_reward
            result_lines.append(f"🏆 <b>ПОБЕДА!</b>")
            result_lines.append(f"💎 +{dust_reward} пыли")

            # Шанс карточки — только из состава группировки
            got_card = random.randint(1, 100) <= cfg.drop_chance
            if got_card:
                from app.data.characters import CHARACTERS, RANK_EMOJI, RANK_CONFIG_MAP
                # Множества для O(1) поиска вместо O(n) на списках
                member_set = set(cfg.members)
                rank_set = set(cfg.drop_ranks)
                candidates = [
                    c for c in CHARACTERS
                    if c["name"] in member_set and c["rank"] in rank_set
                ]
                if not candidates:
                    candidates = [c for c in CHARACTERS if c["name"] in member_set]
                if candidates:
                    weights = [
                        _EMPEROR_WEIGHTS.get(c["rank"], RANK_CONFIG_MAP[c["rank"]].weight)
                        for c in candidates
                    ]
                    char = random.choices(candidates, weights=weights, k=1)[0]
                    from app.models.character import UserCharacter
                    from app.constants.cards import LEVEL_MULTIPLIERS
                    level = 0
                    base_power = char["power"]
                    power_val = int(base_power * LEVEL_MULTIPLIERS[level])
                    new_char = UserCharacter(
                        user_id=user.id,
                        character_id=char["name"],
                        rank=char["rank"],
                        base_power=base_power,
                        power=power_val,
                        level=level,
                    )
                    session.add(new_char)
                    from app.repositories.squad_repo import squad_repo
                    await squad_repo.update_user_combat_power(session, user)
                    rank_emoji = RANK_EMOJI.get(char["rank"], "⭐")
                    result_lines.append(f"🃏 Дроп: {rank_emoji} <b>{char['name']}</b>")
                    dropped_char = char

            rec.defeat_count += 1
            new_power = _gang_power(cfg, rec.defeat_count)
            result_lines.append(f"\n💹 Группировка усилилась до {fmt_num(new_power)} (+20%)")

        else:
            consolation_dust = random.randint(5, 15)
            user.card_dust += consolation_dust
            result_lines.append(f"💀 <b>ПОРАЖЕНИЕ</b>")
            result_lines.append(f"Группировка оказалась сильнее. Прокачайся и попробуй снова!")
            result_lines.append(f"💎 +{consolation_dust} пыли (утешительная)")

        # Двойной удар (навык Монстра): первый удар не ставит КД — второй ставит
        if user.emperor_gang_multi_attack and not rec.multi_attack_used:
            rec.multi_attack_used = True
            result_lines.append("\n⚡ <b>Двойной удар!</b> Можешь атаковать снова!")
        else:
            rec.cooldown_until = now + timedelta(seconds=effective_cd)
            rec.multi_attack_used = False
            cd_line = f"⏳ КД: {fmt_ttl(effective_cd)}"
            if speed_pct:
                cd_line += f" (скорость -{speed_pct}%)"
            result_lines.append(cd_line)

        await session.flush()

        text = "\n".join(result_lines)
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="◀️ К группировкам", callback_data="emperor_gangs"
        ))
        kb = builder.as_markup()

        if dropped_char:
            from app.bot_instance import get_bot
            from app.utils.card_sender import send_card_photo
            bot = get_bot()
            sent = await send_card_photo(
                bot=bot,
                chat_id=cb.message.chat.id,
                char_name=dropped_char["name"],
                caption=text,
                reply_markup=kb,
            )
            if sent:
                try:
                    await cb.message.delete()
                except Exception:
                    pass
                await cb.answer()
                return

        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        await cb.answer()

    finally:
        await cooldown_service.release_lock(lock_key)
