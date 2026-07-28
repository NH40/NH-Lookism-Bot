from datetime import datetime, timedelta, timezone
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.business_service import business_service
from app.utils.formatters import fmt_num, progress_bar
from app.utils.menu_media import safe_edit

PATH_INFO = {
    "legal": {
        "name": "Легальный",
        "emoji": "⚖️",
        "desc": "Стабильный доход, влияние не меняется",
        "color": "🟢",
    },
    "illegal": {
        "name": "Нелегальный",
        "emoji": "🕶",
        "desc": "Доход выше, но волатильный. −Влияние с каждым захваченным районом",
        "color": "🔴",
    },
    "political": {
        "name": "Политика",
        "emoji": "🏛",
        "desc": "Доход ниже, но +влияние с каждым захваченным районом",
        "color": "🔵",
    },
    "digital": {
        "name": "Цифровой",
        "emoji": "💻",
        "desc": "Соло слабее, но сеть своих районов поднимает доход выше легального",
        "color": "🟣",
    },
}


async def _build_business_main(
    session: AsyncSession, user: User
) -> tuple[str, "InlineKeyboardMarkup"]:
    """Чистый билдер (текст, клавиатура) без зависимости от CallbackQuery —
    переиспользуется и инлайн-хэндлером, и быстрым меню (reply-клавиатура)."""
    info = await business_service.get_income_breakdown(session, user)
    path_info = PATH_INFO.get(info["building_path"], {})

    bonuses = []
    if info.get('network_bonus'):
        sign = "+" if info['network_bonus'] >= 0 else ""
        bonuses.append(f"🌐 Сеть {sign}{info['network_bonus']}%")
    if info.get('skills_bonus'):
        bonuses.append(f"📊 Донаты/титулы/мастерство +{info['skills_bonus']}%")
    if info['prestige_bonus']:
        bonuses.append(f"🌟 Пробуждение +{info['prestige_bonus']}%")
    if info['potion_bonus']:
        bonuses.append(f"🧪 Зелье +{info['potion_bonus']}%")
    if info.get('clan_income_bonus'):
        bonuses.append(f"🏯 Клан (улучшения) +{info['clan_income_bonus']}%")
    if info.get('clan_land_income_bonus'):
        bonuses.append(f"🏰 Клан-земли (здания) +{info['clan_land_income_bonus']}%")
    if info.get('clan_donat_income_bonus'):
        bonuses.append(f"💎 Клан-донат +{info['clan_donat_income_bonus']}%")
    if info.get('clan_head_income_bonus'):
        bonuses.append(f"👑 Глава клана +{info['clan_head_income_bonus']}%")
    if info.get('suzerain_bonus'):
        bonuses.append(f"🫡 Вассалы +{info['suzerain_bonus']}%")
    if info['district_multiplier'] != 1.0:
        bonuses.append(f"✖️ Районы x{info['district_multiplier']:.1f}")

    bonus_section = ""
    if bonuses:
        bonus_section = "\n\n━━━ 📊 Прочие бонусы ━━━\n" + "\n".join(bonuses)

    # Сет Славы «Чарльз Чой» — не в общей сумме %, а последним множителем
    # поверх уже готового итога (см. business_service._charles_bonus_percent).
    charles_lines = []
    if info.get('nhn_bonus'):
        charles_lines.append(f"  🏢 Слава NHN +{info['nhn_bonus']}%")
    if info.get('geniuses_bonus'):
        charles_lines.append(f"  🎓 Слава «10 гениев» +{info['geniuses_bonus']}%")
    charles_section = ""
    if charles_lines:
        charles_section = (
            "\n\n━━━ 👑 Сет Славы «Чарльз Чой» ━━━\n"
            "<i>Применяется последним, поверх итога сверху</i>\n"
            + "\n".join(charles_lines)
            + f"\n  ✖️ Итоговый множитель: +{info.get('charles_bonus_pct', 0)}%"
        )

    influence_note = ""
    if info["building_path"] == "illegal":
        influence_note = "  <i>⚠️ −влияние за каждый захваченный район</i>\n"
    elif info["building_path"] == "political":
        influence_note = "  <i>✅ +влияние за каждый захваченный район</i>\n"

    circ_line = ""
    circ_passive = info.get("circ_passive_income", 0)
    if circ_passive:
        circ_per_min = info.get("circ_passive_per_min", 0) or circ_passive
        circ_line = f"\n💸 Пассивный: +{fmt_num(circ_per_min)}/мин"

    vassal_line = ""
    vassal_income = info.get("vassal_tribute_income", 0)
    if vassal_income:
        vassal_line = f"\n🫡 От вассалов: +{fmt_num(vassal_income)}/мин"

    archangel_timer_line = ""
    if getattr(user, "circ_daily_districts", 0) > 0:
        last_at = getattr(user, "circ_daily_districts_at", None)
        now = datetime.now(timezone.utc)
        if last_at is None:
            next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            remaining_first = (next_midnight - now).total_seconds()
            h0, rem0 = divmod(int(remaining_first), 3600)
            m0, s0 = divmod(rem0, 60)
            archangel_timer_line = f"\n👼 Город Архангела (64р.): через <b>{h0}ч {m0}м {s0}с</b>"
        else:
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)
            next_at = last_at + timedelta(hours=24)
            remaining = (next_at - now).total_seconds()
            if remaining <= 0:
                archangel_timer_line = "\n👼 Город Архангела (64р.): <b>готово!</b>"
            else:
                h, rem = divmod(int(remaining), 3600)
                m, s = divmod(rem, 60)
                archangel_timer_line = f"\n👼 Город Архангела (64р.): через <b>{h}ч {m}м {s}с</b>"

    extra_income_lines = [l for l in (circ_line, vassal_line, archangel_timer_line) if l]
    extra_income_section = ""
    if extra_income_lines:
        extra_income_section = "\n\n━━━ 🌐 Доп. доход ━━━" + "".join(extra_income_lines)

    genius_lines = [
        f"🎖 Уровень {progress_bar(info['genius_level'], 10)} {info['genius_level']}/10 (+{info['genius_level_bonus']}%)",
        f"📦 Вместимость {progress_bar(info['genius_capacity_level'], 5)} {info['genius_capacity_level']}/5 (+{info['genius_capacity_bonus']}%)",
        f"💹 Бонус к доходу {progress_bar(info['genius_income_level'], 5)} {info['genius_income_level']}/5 (+{info['genius_income_bonus']}%)",
    ]

    overall_pct = ""
    if info["base_income"] > 0:
        pct = round((info["final_income"] / info["base_income"] - 1) * 100)
        sign = "+" if pct >= 0 else ""
        overall_pct = f" ({sign}{pct}%)"

    text = (
        f"🏢 <b>Бизнес</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 {path_info.get('color', '')} {info.get('building_emoji', '')} <b>{info.get('building_name', '')}</b>"
        f" ({path_info.get('name', '')})\n"
        f"{influence_note}"
        f"🏘 Районов: <b>{info['district_count']}</b> × {fmt_num(info['per_district_rate'])}/район\n\n"
        f"━━━ 🎖 Гений бизнеса ━━━\n"
        + "\n".join(genius_lines) +
        f"\n\n━━━ 💰 Доход ━━━\n"
        f"Базовый:  <b>{fmt_num(info['base_income'])}</b>/мин\n"
        f"Итоговый: <b>{fmt_num(info['final_income'])}</b>/мин{overall_pct}"
        f"{bonus_section}"
        f"{charles_section}"
        f"{extra_income_section}"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"🎖 Гений бизнеса", callback_data="biz_genius_menu"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    return text, builder.as_markup()


async def _show_business_main(
    cb: CallbackQuery, session: AsyncSession, user: User
) -> None:
    text, kb = await _build_business_main(session, user)
    await safe_edit(cb, text, kb)
