"""
Хэндлеры системы Боссов.
"""
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.boss_service import (
    boss_service,
    fmt_hp,
    hp_bar,
    get_boss_attack_cd,
)
from app.constants.bosses import BOSS_MAP, BOSS_TOP_REWARDS, BOSS_PARTICIPANT_REWARD
from app.utils.formatters import fmt_num, fmt_ttl

router = Router()

# ── Изображения боссов ────────────────────────────────────────────────────────

BOSS_IMAGE_MAP: dict[str, str] = {
    "nikita":    "images/boss/Nikita.png",
    "archangel": "images/boss/Arhangel.png",
    "manager":   "images/boss/Meneger.png",
    "brothers":  "images/boss/Brother.png",
}


def _boss_photo(boss_id: str) -> FSInputFile | None:
    """Возвращает FSInputFile для изображения босса или None."""
    path = BOSS_IMAGE_MAP.get(boss_id)
    if path and Path(path).exists():
        return FSInputFile(path)
    return None


# ── Вспомогательные ───────────────────────────────────────────────────────────

def _progress_bar_str(current: int, maximum: int) -> str:
    bar = hp_bar(max(0, current), maximum)
    pct = max(0.0, current / maximum * 100) if maximum > 0 else 0.0
    return f"[{bar}] {pct:.1f}%"


async def _boss_main_screen(
    session: AsyncSession, user: User
) -> tuple[str, any, str | None]:
    """Возвращает (текст, клавиатура, boss_id | None) для главного экрана боссов."""
    from app.repositories.boss_repo import boss_repo
    from app.services.cooldown_service import cooldown_service

    boss = await boss_service.get_current_boss(session)
    builder = InlineKeyboardBuilder()

    # ── Нет активного босса ───────────────────────────────────────────────────
    if boss is None:
        next_at = await boss_service.get_next_spawn_at(session)
        now = datetime.now(timezone.utc)

        if next_at and next_at > now:
            secs = int((next_at - now).total_seconds())
            time_line = f"⏳ Следующий босс через: <b>{fmt_ttl(secs)}</b>"
        else:
            time_line = "⏳ Босс появится совсем скоро..."

        text = (
            f"⚔️ <b>Боссы</b>\n\n"
            f"Сейчас активного босса нет.\n\n"
            f"{time_line}\n\n"
            f"Включи уведомления, чтобы не пропустить появление!"
        )
        builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
        return text, builder.as_markup(), None

    # ── Активный босс ─────────────────────────────────────────────────────────
    cfg = BOSS_MAP.get(boss.boss_id)
    now = datetime.now(timezone.utc)
    time_left = max(0, int((boss.expires_at - now).total_seconds()))

    # Состояние для особых боссов
    state = boss.get_state()
    extra_lines: list[str] = []

    if boss.boss_id == "nikita":
        despair = state.get("despair_scale", 0.0)
        heal_count = state.get("heal_count", 0)
        extra_lines.append(
            f"🔴 Шкала отчаяния: <b>{despair:.1f}%</b> "
            f"{'█' * int(despair / 10)}{'░' * (10 - int(despair / 10))}\n"
            f"   Исцелений: {heal_count}"
        )
    elif boss.boss_id == "archangel":
        shield = state.get("shield_hp", 0)
        debuff = state.get("debuff_attacks", 0)
        if shield > 0:
            extra_lines.append(f"🛡 Щит: <b>{fmt_hp(shield)}</b>")
        if debuff > 0:
            extra_lines.append(f"⬇️ Дебафф урона: <b>{debuff}</b> атак осталось")
    elif boss.boss_id == "manager":
        healed = state.get("healed", False)
        if healed:
            extra_lines.append("💊 Менеджер уже использовал самолечение!")

    # HP бар
    display_hp = boss.hp if boss.boss_id != "brothers" else boss.hp
    bar_str = _progress_bar_str(max(0, display_hp), boss.current_max_hp)

    hp_line = (
        f"❤️ HP: <b>{fmt_hp(display_hp)}</b> / {fmt_hp(boss.current_max_hp)}\n"
        f"{bar_str}"
    )
    if boss.boss_id == "brothers" and boss.hp < 0:
        hp_line = (
            f"❤️ HP: <b>{fmt_hp(boss.hp)}</b> ← в минусе!\n"
            f"{'░' * 16} 0%"
        )

    extra_str = "\n".join(extra_lines)
    if extra_str:
        extra_str = "\n" + extra_str + "\n"

    text = (
        f"⚔️ <b>Боссы</b>\n\n"
        f"{cfg.emoji} <b>{cfg.name}</b>\n"
        f"<i>{cfg.desc}</i>\n\n"
        f"{hp_line}"
        f"{extra_str}\n"
        f"⏳ До конца: <b>{fmt_ttl(time_left)}</b>\n\n"
        f"{cfg.special_desc}\n"
    )

    # Кнопка атаки с КД
    cd_key = f"boss:attack:{user.id}"
    cd_ttl = await cooldown_service.get_ttl(cd_key)
    if cd_ttl > 0:
        builder.row(InlineKeyboardButton(
            text=f"⏳ КД атаки: {fmt_ttl(cd_ttl)}",
            callback_data="boss_cd_info",
        ))
    else:
        builder.row(InlineKeyboardButton(
            text=f"⚔️ Атаковать {cfg.emoji} {cfg.name}",
            callback_data=f"boss_attack:{boss.id}",
        ))

    builder.row(InlineKeyboardButton(
        text="🏆 Топ урона", callback_data="boss_top"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    return text, builder.as_markup(), boss.boss_id


# ── Вспомогательная отправка экрана босса ────────────────────────────────────

async def _send_boss_screen(
    cb: CallbackQuery,
    session: AsyncSession,
    user: User,
) -> None:
    """
    Удаляет текущее сообщение и отправляет экран босса:
    - с фото (если есть изображение для активного босса)
    - или текстом (если босс неактивен / нет картинки)
    """
    text, kb, boss_id = await _boss_main_screen(session, user)
    photo = _boss_photo(boss_id) if boss_id else None

    # Удаляем старое сообщение
    try:
        await cb.message.delete()
    except Exception:
        pass

    if photo:
        await cb.message.answer_photo(
            photo,
            caption=text,
            reply_markup=kb,
            parse_mode="HTML",
        )
    else:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")


# ── Главный экран ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "bosses_menu")
async def cb_bosses_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    await _send_boss_screen(cb, session, user)
    await cb.answer()


@router.callback_query(F.data == "boss_cd_info")
async def cb_boss_cd_info(cb: CallbackQuery, user: User):
    from app.services.cooldown_service import cooldown_service
    cd_key = f"boss:attack:{user.id}"
    ttl = await cooldown_service.get_ttl(cd_key)
    if ttl > 0:
        await cb.answer(f"⏳ КД атаки: {fmt_ttl(ttl)}", show_alert=True)
    else:
        await cb.answer("Можно атаковать!")


# ── Атака ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("boss_attack:"))
async def cb_boss_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    try:
        boss_record_id = int(cb.data.split(":")[1])
    except (IndexError, ValueError):
        await cb.answer("Ошибка", show_alert=True)
        return

    from app.services.cooldown_service import cooldown_service

    lock_key = cooldown_service.boss_attack_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=15):
        await cb.answer("⏳ Атака уже обрабатывается", show_alert=True)
        return

    try:
        # Проверяем КД
        cd_key = f"boss:attack:{user.id}"
        ttl = await cooldown_service.get_ttl(cd_key)
        if ttl > 0:
            await cb.answer(f"⏳ КД: {fmt_ttl(ttl)}", show_alert=True)
            return

        # Проверяем, что босс ещё активен и совпадает с кнопкой
        boss = await boss_service.get_current_boss(session)
        if not boss or boss.id != boss_record_id:
            await cb.answer("Босс уже не активен!", show_alert=True)
            await _send_boss_screen(cb, session, user)
            await cb.answer()
            return

        # Выполняем атаку
        result = await boss_service.attack(session, user, boss)

        if not result["ok"]:
            await cb.answer(result["reason"], show_alert=True)
            return

        # Устанавливаем КД (с учётом cd_multiplier от Архангела)
        base_cd = get_boss_attack_cd(user)
        final_cd = int(base_cd * result["cd_multiplier"])
        await cooldown_service.set_cooldown(cd_key, final_cd)

        from app.utils.region_activity import record
        await record(session, user.id, "boss")

        cfg = BOSS_MAP.get(boss.boss_id)
        boss_defeated = result["boss_defeated"]

        # Строим сообщение результата атаки
        lines = [
            f"⚔️ <b>Удар по {cfg.emoji} {cfg.name}!</b>\n",
            f"💥 Урон: <b>{fmt_hp(result['damage'])}</b>",
        ]

        if result["special_effects"]:
            lines.append("")
            lines.extend(result["special_effects"])

        lines.append("")
        lines.append(f"<i>«{result['phrase']}»</i>")
        lines.append("")

        if boss_defeated:
            lines.append(f"🏆 <b>БОСС ПОВЕРЖЕН!</b> Награды будут начислены!")
        else:
            hp_now = result["boss_hp"]
            hp_max = result["boss_max_hp"]
            if boss.boss_id == "brothers" and hp_now < 0:
                lines.append(f"❤️ HP братьев: <b>{fmt_hp(hp_now)}</b> ← отрицательный!")
            else:
                lines.append(f"❤️ HP: <b>{fmt_hp(hp_now)}</b> / {fmt_hp(hp_max)}")
                lines.append(_progress_bar_str(max(0, hp_now), hp_max))

        if result["cd_multiplier"] > 1.0:
            lines.append(f"\n⏳ КД удвоен Архангелом: <b>{fmt_ttl(final_cd)}</b>")
        else:
            lines.append(f"\n⏳ Следующая атака через: <b>{fmt_ttl(final_cd)}</b>")

        text = "\n".join(lines)

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="🔄 К боссу", callback_data="bosses_menu"
        ))
        builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await cb.answer(f"Удар нанесён! -{fmt_hp(result['damage'])}")

    finally:
        await cooldown_service.release_lock(lock_key)


# ── Топ атакующих ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "boss_top")
async def cb_boss_top(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.repositories.boss_repo import boss_repo

    boss = await boss_service.get_current_boss(session)
    if not boss:
        await cb.answer("Нет активного босса", show_alert=True)
        return

    cfg = BOSS_MAP.get(boss.boss_id)
    top = await boss_repo.get_top_attackers(session, boss.id, limit=10)

    if not top:
        await cb.answer("Ещё никто не атаковал!", show_alert=True)
        return

    # Подгружаем имена
    from sqlalchemy import select
    from app.models.user import User as UserModel

    user_ids = [r.user_id for r in top]
    users_result = await session.execute(
        select(UserModel).where(UserModel.id.in_(user_ids))
    )
    users_map = {u.id: u for u in users_result.scalars().all()}

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = [f"🏆 <b>Топ атакующих {cfg.emoji} {cfg.name}</b>\n"]
    for i, rec in enumerate(top):
        u = users_map.get(rec.user_id)
        name = u.full_name if u else f"Игрок #{rec.user_id}"
        reward = BOSS_TOP_REWARDS[i] if i < len(BOSS_TOP_REWARDS) else BOSS_PARTICIPANT_REWARD
        lines.append(
            f"{medals[i]} {name}\n"
            f"   ⚔️ {fmt_hp(rec.damage_dealt)} урона | 🎟 {reward} тикетов"
        )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К боссу", callback_data="bosses_menu"))

    try:
        await cb.message.edit_text(
            "\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(
            "\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    await cb.answer()
