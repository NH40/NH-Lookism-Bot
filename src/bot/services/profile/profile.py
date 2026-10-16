"""Экран «Профиль» — статистика, характеристики, мастерство, выбор уникальной техники/пути/родословной/гениальности/пробуждения, кнопка удаления банды (сервис).

Пока показывает только то, что реально существует (регистрация + страна/город/фаза +
название банды) — характеристики/мастерство/клан/мощь/влияние появятся, когда будут
реализованы соответствующие домены (см. CLAUDE.md, "Открытые вопросы дизайна" — раздел
«Профиль» в raw-notes сильно недоспецифицирован, додумывать несуществующие числа сейчас
не нужно, honest MVP лучше выдуманного).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.country import CountryDef
from bot.db.models.city import City
from bot.db.repositories.user import get_by_id
from bot.db.repositories import clan as clan_repo
from bot.services.business import get_wallet
from bot.services.characteristic import StatsView, get_combat_profile, get_stats_view
from bot.services.bloodline import BloodlineState
from bot.services.bloodline import get_state as get_bloodline_state
from bot.services.ticket import TicketStatus
from bot.services.ticket import get_status as get_ticket_status
from bot.services.city import get_city
from bot.services.country import get_country
from bot.services.district import get_territory
from bot.services.extra import get_army_stats
from bot.services.gang import get_gang


@dataclass(frozen=True, slots=True)
class ProfileView:
    user_id: int
    username: str | None
    display_name: str | None
    is_onboarded: bool
    country: CountryDef | None
    city: City | None
    phase: str
    gang_name: str | None
    clan_name: str | None
    army_power: int
    districts: int
    influence: int
    nh_coins: int
    nh_coins_pending: int
    stats: StatsView
    mastery: dict[str, int]
    tickets: TicketStatus
    bloodline: BloodlineState


async def _clan_name(session: AsyncSession, user_id: int) -> str | None:
    member = await clan_repo.get_member(session, user_id)
    clan = await clan_repo.get(session, member.clan_id) if member else None
    return clan.name if clan else None


async def get_profile(session: AsyncSession, user_id: int) -> ProfileView | None:
    """«Мощь» из raw-notes профиля пока = мощь армии статистов: остальные слагаемые
    (ранг Силы +1%/ранг, мастерство Силы, уникальные персонажи — домен `power`) ещё не
    реализованы, поэтому поле честно называется `army_power`, а не просто "мощь"."""
    user = await get_by_id(session, user_id)
    if user is None:
        return None

    country = get_country(user.country_code) if user.country_code else None
    city = await get_city(session, user.city_id) if user.city_id is not None else None
    gang = await get_gang(session, user_id)
    army = await get_army_stats(session, user_id)
    territory = await get_territory(session, user_id)
    wallet = await get_wallet(session, user_id)
    stats = await get_stats_view(session, user_id)
    mastery = (await get_combat_profile(session, user_id)).mastery
    tickets = await get_ticket_status(session, user_id)

    return ProfileView(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_onboarded=user.city_id is not None,
        country=country,
        city=city,
        phase=user.phase,
        gang_name=gang.name if gang else None,
        clan_name=await _clan_name(session, user_id),
        army_power=army.total_power,
        districts=territory.districts,
        influence=territory.influence,
        nh_coins=wallet.nh_coins,
        nh_coins_pending=wallet.pending,
        stats=stats,
        mastery=mastery,
        tickets=tickets,
        bloodline=await get_bloodline_state(session, user_id),
    )
