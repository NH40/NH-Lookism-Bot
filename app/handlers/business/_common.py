from datetime import datetime, timedelta, timezone
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.business_service import business_service
from app.utils.formatters import fmt_num, progress_bar, pair_lines

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
        "desc": "−Влияние при постройке, +влияние при сносе. Лучший доход",
        "color": "🔴",
    },
    "political": {
        "name": "Политика",
        "emoji": "🏛",
        "desc": "+Влияние при постройке, −влияние при сносе",
        "color": "🔵",
    },
    "digital": {
        "name": "Цифровой",
        "emoji": "💻",
        "desc": "Дешёвые районы + Сетевой эффект: +10% доход за каждые 10 зданий (макс +50%)",
        "color": "🟣",
    },
}


async def _show_business_main(
    cb: CallbackQuery, session: AsyncSession, user: User
) -> None:
    info = await business_service.get_income_breakdown(session, user)
    path_info = PATH_INFO.get(user.business_path, {})

    biz_genius = getattr(user, "business_genius_level", 0)
    biz_frags = getattr(user, "business_fragments", 0)
    bonus_districts = getattr(user, "bonus_business_districts", 0)

    # Бонусы к доходу (гений бизнеса уже показан отдельной строкой выше — не дублируем)
    bonuses = []
    if info.get('network_bonus'):
        bonuses.append(f"🌐 Сеть +{info['network_bonus']}%")
    if info.get('skills_bonus'):
        bonuses.append(f"📊 Титул +{info['skills_bonus']}%")
    if info['prestige_bonus']:
        bonuses.append(f"🌟 Пробуждение +{info['prestige_bonus']}%")
    if info['potion_bonus']:
        bonuses.append(f"🧪 Зелье +{info['potion_bonus']}%")
    if info.get('clan_income_bonus'):
        bonuses.append(f"🏯 Клан +{info['clan_income_bonus']}%")
    if info.get('clan_donat_income_bonus'):
        bonuses.append(f"💎 Клан-донат +{info['clan_donat_income_bonus']}%")
    if info['district_multiplier'] != 1.0:
        bonuses.append(f"✖️ Районы x{info['district_multiplier']:.1f}")

    bonus_section = ""
    if bonuses:
        bonus_section = "\n\n━━━ 📊 Бонусы к доходу ━━━\n" + "\n".join(pair_lines(bonuses))

    # Влияние пути
    influence_note = ""
    if user.business_path == "illegal":
        influence_note = "  <i>⚠️ −влияние за постройку</i>\n"
    elif user.business_path == "political":
        influence_note = "  <i>✅ +влияние за постройку</i>\n"

    # Пассивный доход от циркуляции
    circ_line = ""
    circ_passive = info.get("circ_passive_income", 0)
    if circ_passive:
        circ_per_min = info.get("circ_passive_per_min", 0) or circ_passive
        circ_line = f"\n💸 Пассивный: +{fmt_num(circ_per_min)}/мин"

    # Доход от зданий клана в регионе (с бонусами владельца)
    clan_bld_line = ""
    clan_bld_income = getattr(user, "clan_region_income", 0)
    if clan_bld_income:
        from sqlalchemy import select as sa_select
        from app.models.clan import Clan, ClanMember
        effective_bld = clan_bld_income
        try:
            cm = await session.scalar(
                sa_select(ClanMember).where(ClanMember.user_id == user.id)
            )
            if cm:
                clan = await session.scalar(sa_select(Clan).where(Clan.id == cm.clan_id))
                if clan:
                    from app.models.user import User as UserModel
                    owner = await session.scalar(
                        sa_select(UserModel).where(UserModel.id == clan.owner_id)
                    )
                    if owner:
                        owner_bonus = (
                            (owner.income_bonus_percent or 0)
                            + (owner.prestige_income_bonus or 0)
                            + (owner.clan_income_bonus or 0)
                            + (owner.clan_donat_income_bonus or 0)
                            + (owner.region_income_pct or 0)
                            + (owner.region_income_building_pct or 0)
                        )
                        effective_bld = max(0, int(clan_bld_income * (1 + owner_bonus / 100)))
        except Exception:
            pass
        clan_bld_line = f"\n🏗 Здания клана: +{fmt_num(effective_bld)}/мин"

    # Таймер ежедневного города Архангела (круг 10)
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

    from app.constants.raid import BIZ_GENIUS_LEVEL_LABELS, BIZ_GENIUS_DISCOUNT, BIZ_GENIUS_INCOME_BONUS
    genius_label = BIZ_GENIUS_LEVEL_LABELS.get(biz_genius, "") if biz_genius > 0 else "не открыт"
    genius_discount = BIZ_GENIUS_DISCOUNT[biz_genius - 1] if biz_genius > 0 else 0
    genius_income_b = BIZ_GENIUS_INCOME_BONUS[biz_genius - 1] if biz_genius > 0 else 0
    genius_perks = []
    if genius_income_b:
        genius_perks.append(f"+{genius_income_b}% доход")
    if genius_discount:
        genius_perks.append(f"-{genius_discount}% стройка")
    genius_perks_str = f"\n   {', '.join(genius_perks)}" if genius_perks else ""
    genius_label_str = f" — {genius_label}" if genius_label else ""

    # Дополнительная информация (районы/фрагменты)
    extra_bits = []
    if bonus_districts:
        extra_bits.append(f"🏘 Районов: {bonus_districts}/50")
    if biz_frags:
        extra_bits.append(f"🧩 Фрагментов: {biz_frags}")
    extra_line = f"\n{' | '.join(extra_bits)}" if extra_bits else ""

    # Дополнительный доход (пассивный/клан/архангел) — отдельным блоком
    extra_income_lines = [l for l in (circ_line, clan_bld_line, archangel_timer_line) if l]
    extra_income_section = ""
    if extra_income_lines:
        extra_income_section = "\n\n━━━ 🌐 Доп. доход ━━━" + "".join(extra_income_lines)

    overall_pct = ""
    if info["base_income"] > 0:
        pct = round((info["final_income"] / info["base_income"] - 1) * 100)
        overall_pct = f" (+{pct}%)"

    text = (
        f"🏢 <b>Бизнес</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 {path_info.get('color','')} {path_info.get('emoji','')} <b>{path_info.get('name','')}</b>\n"
        f"{influence_note}"
        f"🎖 Гений бизнеса {progress_bar(biz_genius, 5)} {biz_genius}/5{genius_label_str}"
        f"{genius_perks_str}"
        f"{extra_line}\n\n"
        f"━━━ 💰 Доход ━━━\n"
        f"Базовый:  <b>{fmt_num(info['base_income'])}</b>/мин\n"
        f"Итоговый: <b>{fmt_num(info['final_income'])}</b>/мин{overall_pct}"
        f"{bonus_section}"
        f"{extra_income_section}"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏗 Построить",    callback_data="biz_build"),
        InlineKeyboardButton(text="🏢 Мои здания",   callback_data="biz_my_buildings"),
    )
    builder.row(InlineKeyboardButton(
        text=f"🎖 Гений бизнеса  [Ур.{biz_genius}/5]", callback_data="biz_genius_menu"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
