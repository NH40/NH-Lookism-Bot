"""Экран «Профиль» — статистика, характеристики, мастерство, выбор уникальной техники/пути/родословной/гениальности/пробуждения, кнопка удаления банды (хендлеры).

`show_profile()` — публичная функция домена (не `_show`), переиспользуется
`handlers/start` (см. CLAUDE.md UAP, "/start у существующего игрока открывает профиль" —
тот же переход портирован сюда).
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import get_settings
from bot.constant.profile import CB_PROFILE_OPEN
from bot.keyboards.profile import profile_menu
from bot.services.empire import get_emperor
from bot.services.phase import is_emperor
from bot.services.profile import get_profile
from bot.config.mastery import MASTERY_UNLOCK_RANK_INDEX
from bot.constant.characteristic import MASTERIES, STAT_STRENGTH
from bot.services.characteristic import StatsView
from bot.texts.profile import (
    NOT_ONBOARDED,
    PENDING_LINE,
    PHASE_LABELS,
    DEV_POINTS_LINE,
    MASTERY_LABELS,
    MASTERY_LINE,
    MASTERY_LOCKED,
    MASTERY_OPEN_HINT,
    MASTERY_TIER_LABELS,
    NO_CLAN,
    POTENTIAL_LABELS,
    POTENTIAL_LINE,
    POTION_LINE,
    POTIONS_BLOCK,
    PROFILE_CARD,
    STAT_LABELS,
    STAT_LINE,
    STRENGTH_BONUS,
)
from bot.texts.bloodline import bloodline_line
from bot.texts.gacha import tickets_line
from bot.texts.potion import POTION_NAMES, ROMAN
from bot.texts.development import describe_level
from bot.config.potion import POTION_EFFECTS
from bot.constant.potion import POTIONS
from bot.services.potion import catalog as potion_catalog
from bot.utils.formatting import esc, format_countdown, format_number
from bot.utils.mini_app import resolve_mini_app_base_url

from bot.services.unique_path import award_daily

router = Router(name="profile")


def render_stats_block(stats: StatsView) -> str:
    """Характеристики (raw-notes «Профиль»): ранги, потенциал, очки развития под потенциалом."""
    lines = []
    for stat in stats.stats:
        bonus = (
            STRENGTH_BONUS.format(percent=stats.strength_power_percent)
            if stat.code == STAT_STRENGTH and stats.strength_power_percent
            else ""
        )
        lines.append(STAT_LINE.format(label=STAT_LABELS[stat.code], rank=stat.rank, bonus=bonus))
    lines.append(POTENTIAL_LINE.format(potential=POTENTIAL_LABELS[stats.potential]))
    lines.append(DEV_POINTS_LINE.format(points=format_number(stats.dev_points)))
    return "\n".join(lines)


def render_mastery_block(mastery: dict[str, int], *, unlocked: bool) -> str:
    """Мастерство — 4 ветки по 3 ступени; пока характеристики не дошли до EXR — подсказка,
    как открыть цепочку «Преодоление стены» (`unlocked` — все четыре ≥ EXR)."""
    lines = [
        MASTERY_LINE.format(
            label=MASTERY_LABELS[code],
            tier=MASTERY_TIER_LABELS[mastery[code]],
        )
        for code in MASTERIES
    ]
    lines.append(MASTERY_OPEN_HINT if unlocked else MASTERY_LOCKED)
    return "\n".join(lines)


async def _potions_block(session: AsyncSession, user_id: int) -> str:
    """Действующие зелья с остатком срока и эффектом — пусто, если ни одно не действует."""
    active = [st for st in (await potion_catalog(session, user_id)).states.values() if st.tier]
    if not active:
        return ""
    lines = [
        POTION_LINE.format(
            name=POTION_NAMES[st.kind], roman=ROMAN[st.tier], countdown=format_countdown(st.left_seconds),
            effect=describe_level(POTION_EFFECTS[st.kind][1][st.tier - 1]),
        )
        for st in sorted(active, key=lambda st: POTIONS.index(st.kind))
    ]
    return POTIONS_BLOCK.format(lines="\n".join(lines))


async def show_profile(message: Message, session: AsyncSession, user_id: int) -> None:
    profile = await get_profile(session, user_id)
    if profile is None or not profile.is_onboarded:
        await message.answer(NOT_ONBOARDED)
        return
    # Очки пути за ежедневный заход (интервал источника, только при пробуждённом пути).
    await award_daily(session, user_id)

    settings = get_settings()
    mini_app_url = resolve_mini_app_base_url(settings.mini_app_url, message.chat.type)
    await message.answer(
        PROFILE_CARD.format(
            display_name=esc(profile.display_name or "—"),
            username=f"@{esc(profile.username)}" if profile.username else "—",
            gang_name=esc(profile.gang_name or "—"),
            country=profile.country.name if profile.country else "—",
            city=profile.city.name if profile.city else "—",
            phase_label=PHASE_LABELS.get(profile.phase, profile.phase),
            army_power=format_number(profile.army_power),
            influence=profile.influence,
            districts=profile.districts,
            nh_coins=format_number(profile.nh_coins),
            pending_line=(
                PENDING_LINE.format(pending=format_number(profile.nh_coins_pending))
                if profile.nh_coins_pending
                else ""
            ),
            stats_block=render_stats_block(profile.stats),
            mastery_block=render_mastery_block(
                profile.mastery, unlocked=min(s.index for s in profile.stats.stats) >= MASTERY_UNLOCK_RANK_INDEX
            ),
            clan=esc(profile.clan_name) if profile.clan_name else NO_CLAN,
            bloodline_line=bloodline_line(
                profile.bloodline.code, profile.bloodline.level, profile.bloodline.blood_drops
            ),
            tickets_line=tickets_line(profile.tickets.count, profile.tickets.cap, profile.tickets.next_in_seconds),
            potions_block=await _potions_block(session, user_id),
        ),
        reply_markup=profile_menu(
            mini_app_url=mini_app_url,
            emperor=is_emperor(profile.phase),
            under_emperor=await get_emperor(session, user_id) is not None,
        ),
    )


@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession) -> None:
    await show_profile(message, session, message.from_user.id)


@router.callback_query(F.data == CB_PROFILE_OPEN)
async def cb_profile_open(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await show_profile(callback.message, session, callback.from_user.id)
