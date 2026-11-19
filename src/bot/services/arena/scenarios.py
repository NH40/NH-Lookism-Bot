"""Сценарии онлайн-боя (2026-11-19, этап 4): старт боя из игрового действия и применение итога.

Итог применяет та же функция, что и у автобоя (`settle_*`), — правила игры не дублируются. Сессию БД финишер
открывает сам (бой заканчивается в любом процессе: API, бот, фоновый проход) — фабрику задаёт `set_session_factory`.
"""
from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.services.arena import arena as core

KIND_DISTRICT = "district"
_SF: dict[str, async_sessionmaker[AsyncSession]] = {}


def set_session_factory(sf: async_sessionmaker[AsyncSession]) -> None:
    _SF["sf"] = sf


async def _name(session: AsyncSession, user_id: int) -> str:
    from bot.db.repositories.gang import get_by_user

    gang = await get_by_user(session, user_id)
    return gang.name if gang else "—"


async def start_district(session: AsyncSession, redis: Redis, user, district_id: int, *, auto: bool = False) -> dict:
    """Онлайн-бой за район ботов. Проверки и КД — те же, что у автобоя."""
    from bot.services.arena.sources import energy_for, perks_for
    from bot.services.district import prepare_attack

    if await core.current_of(redis, user.id):
        raise core.ArenaError("in_battle")
    prep = await prepare_attack(session, redis, user, district_id)
    m = prep.matchup
    st = await core.create(
        redis, kind=KIND_DISTRICT, a_uid=user.id, d_uid=None, a_stacks=prep.stacks, d_stacks=prep.defender,
        a_chances=m.attacker, d_chances=m.defender, a_perks=await perks_for(session, user.id), d_perks=[],
        a_auto=auto, d_auto=True, a_name=await _name(session, user.id), d_name=f"Боты района {prep.row.number}",
        meta={"district_id": district_id}, a_energy=await energy_for(session, user.id),
    )
    await session.rollback()  # снять FOR UPDATE с лагеря — бой идёт без открытой транзакции
    return st


async def _finish_district(redis: Redis, st: dict, result) -> None:
    from bot.config.characteristic import extra_power_for_rank
    from bot.constant.extra import CAMP_ATTACK
    from bot.constant.position_skill import VS_DISTRICT
    from bot.db.models.user import User
    from bot.services.characteristic import get_combat_profile
    from bot.services.combat import CombatStack, base_chances
    from bot.services.district import AttackPrep, settle_attack
    from bot.services.district.army import load_camp
    from bot.services.district.district import _bot_army, get_city, get_row
    from bot.services.position_skill.battle import matchup
    from bot.cache.keys import battle_cooldown

    async with _SF["sf"]() as session:
        user = await session.get(User, st["a"]["uid"])
        row = await get_row(session, st["meta"]["district_id"])
        stacks = await load_camp(session, user.id, CAMP_ATTACK, for_update=True)
        profile = await get_combat_profile(session, user.id)
        city = await get_city(session, row.city_id)
        rank, qty = _bot_army(city.district_count)
        defender = [CombatStack(key="bot", unit_power=extra_power_for_rank(rank), quantity=qty)]
        m = matchup(profile, vs=(VS_DISTRICT,), defender_chances=base_chances(), attacker_stacks=stacks)
        report = await settle_attack(session, redis, user, AttackPrep(row, stacks, defender, profile, m, battle_cooldown(user.id)), result)
    st["report"] = {"won": report.won, "captured": report.captured, "taken_by_other": report.taken_by_other,
                    "district": report.district_number, "dead": report.attacker_dead, "promoted_to": report.promoted_to}
    await core.save(redis, st)


core.register_finisher(KIND_DISTRICT, _finish_district)
