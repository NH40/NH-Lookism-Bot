"""Бой за трон — у страны один император (сервис).

Пользователь 2026-10-01 (`docs/design/fist_emperor.md`): круг, снова взявший все города
страны, где уже есть император, вступает с ним в **обязательное сражение за трон**.
Победитель — император; проигравший теряет фазу (→ банда), районы и бизнес, но сохраняет
выживших статистов и уников, прокачку и ресурсы.

Бой сразу, в той же транзакции, что захват, закрывший страну (без часа на принятие —
«обязательное» сражение): лагерь атаки претендента против лагеря защиты императора, шансы
обеих сторон — из характеристик и мастерства. Стопки блокируются в порядке user_id (как в
PvP), перед потерей бизнеса проигравшему начисляется доход до этой секунды.
"""
from __future__ import annotations

from bot.constant.ledger import BATTLE_THRONE

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.absolute import after_battle
from bot.services.intel.scout import has_report as has_scout_report
from bot.db.repositories.activity.activity import mark_flags
from bot.constant.position_skill import VS_THRONE
from bot.services.position_skill.battle import journal, matchup
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
from bot.constant.ledger import REASON_WAR_TREASURY
from bot.constant.activity import ACT_BATTLE
from bot.services.activity import log as log_activity
from bot.services.activity import remember_opponents
from bot.texts.activity import LOG_THRONE_CONTENDER, LOG_THRONE_INCUMBENT, LOST, WON
from bot.services.business import accrue_many
from bot.services.characteristic import get_combat_profile
from bot.services.combat import simulate_battle
from bot.constant.dev_quest import TASK_WIN_PVP
from bot.services.dev_quest import emit as quest_event
from bot.services.district.army import apply_losses, load_camp
from bot.services.gang import get_gang
from bot.services.phase import check_promotion, crown, demote_to_gang
from bot.config.empire import war_treasury_percent
from bot.db.repositories import empire as empire_repo
from bot.db.repositories import phase as phase_repo
from bot.texts.activity import LOG_LIBERATION_CONTENDER, LOG_LIBERATION_HOLDER


@dataclass(frozen=True, slots=True)
class ThroneOutcome:
    contender_id: int
    incumbent_id: int
    contender_label: str
    incumbent_label: str
    contender_won: bool
    rounds: int
    contender_power: int
    contender_dead: int
    incumbent_power: int
    incumbent_dead: int
    journal: tuple[str, ...] = ()  # журнал боя глазами нападающего (`services/position_skill.journal`)
    defender_journal: tuple[str, ...] = ()  # тот же бой глазами защитника


async def throne_context(session: AsyncSession, contender_id: int, opponent_id: int):
    """Лагерь атаки круга против лагеря защиты противника (трон или освобождение) → (лагеря, matchup).
    Блокирует стопки — вызывающий коммитит или откатывает."""
    sides = sorted([(contender_id, CAMP_ATTACK), (opponent_id, CAMP_DEFENSE)])
    camps = {uid: await load_camp(session, uid, camp, for_update=True) for uid, camp in sides}
    m = matchup(
        await get_combat_profile(session, contender_id), await get_combat_profile(session, opponent_id), vs=(VS_THRONE,),
        scouted=await has_scout_report(session, contender_id, opponent_id),
        marked=await mark_flags(session, contender_id, opponent_id),
        attacker_stacks=camps[contender_id], defender_stacks=camps[opponent_id],
    )
    return camps, m


async def resolve_throne(session: AsyncSession, contender_id: int, incumbent_id: int) -> ThroneOutcome:
    """Бой за трон целиком (мгновенный расчёт; в игре — онлайн-бой, `services/arena.start_throne`). НЕ коммитит."""
    camps, m = await throne_context(session, contender_id, incumbent_id)
    result = simulate_battle(camps[contender_id], camps[incumbent_id], attacker_chances=m.attacker, defender_chances=m.defender)
    return await settle_throne(session, contender_id, incumbent_id, camps, m, result)


async def settle_throne(session: AsyncSession, contender_id: int, incumbent_id: int, camps, m, result) -> ThroneOutcome:
    """Последствия боя за трон (общие для онлайн-боя и мгновенного расчёта). НЕ коммитит."""
    await apply_losses(session, contender_id, CAMP_ATTACK, result.attacker.dead)
    abs_lines = await after_battle(session, m, result, kind=BATTLE_THRONE, attacker_id=contender_id, attacker_stacks=camps[contender_id], defender_id=incumbent_id)
    await apply_losses(session, incumbent_id, CAMP_DEFENSE, result.defender.dead)

    # Доход бизнеса до этой секунды — обоим, пока здания ещё на своих местах.
    await accrue_many(session, [contender_id, incumbent_id])
    if result.attacker_won:
        # Окончательное поражение императора: оставшиеся владения — победителю (2026-10-14),
        # без городов и бизнесов — в банду.
        await phase_repo.transfer_holdings(session, incumbent_id, contender_id, [], 0, everything=True)
        await demote_to_gang(session, incumbent_id)
        await crown(session, contender_id)
    else:
        await demote_to_gang(session, contender_id)

    contender_gang = await get_gang(session, contender_id)
    incumbent_gang = await get_gang(session, incumbent_id)
    won = result.attacker_won
    await log_activity(
        session, contender_id, ACT_BATTLE,
        LOG_THRONE_CONTENDER.format(incumbent=incumbent_gang.name if incumbent_gang else "—", outcome=WON if won else LOST),
    )
    await log_activity(
        session, incumbent_id, ACT_BATTLE,
        LOG_THRONE_INCUMBENT.format(contender=contender_gang.name if contender_gang else "—", outcome=LOST if won else WON),
    )
    await remember_opponents(session, contender_id, incumbent_id)
    if won:
        # Победа над игроком нападающим — как PvP-вызов (пользователь 2026-10-28: трон и
        # освобождение засчитываются заданию «Победить игрока нападающим»).
        await quest_event(session, contender_id, TASK_WIN_PVP)
    return ThroneOutcome(
        journal=journal(result, m.spy) + abs_lines, defender_journal=journal(result, m.spy, viewer_is_attacker=False) + abs_lines,
        contender_id=contender_id,
        incumbent_id=incumbent_id,
        contender_label=contender_gang.name if contender_gang else "—",
        incumbent_label=incumbent_gang.name if incumbent_gang else "—",
        contender_won=result.attacker_won,
        rounds=result.rounds,
        contender_power=result.attacker.initial_power,
        contender_dead=result.attacker.total_dead,
        incumbent_power=result.defender.initial_power,
        incumbent_dead=result.defender.total_dead,
    )


@dataclass(frozen=True, slots=True)
class LiberationOutcome:
    """Бой за освобождение страны с чужим императором, державшим её города."""

    contender_id: int
    holder_id: int
    contender_label: str
    holder_label: str
    contender_won: bool
    rounds: int
    contender_dead: int
    holder_dead: int
    city_names: tuple[str, ...] = ()
    treasury: int = 0
    businesses: int = 0
    holder_demoted: bool = False
    journal: tuple[str, ...] = ()  # журнал боя глазами нападающего (`services/position_skill.journal`)
    defender_journal: tuple[str, ...] = ()  # тот же бой глазами защитника


async def resolve_liberation(session: AsyncSession, contender_id: int, holder_id: int, country_code: str) -> LiberationOutcome:
    """Круг страны против чужого императора, держащего её города (пользователь 2026-10-14):
    лагерь атаки круга против лагеря защиты императора. Победа — города страны освобождаются
    (на коронации станут кругу), доля казны (как в войне императоров, по перевесу) и владения из
    этих городов — кругу; без городов и бизнесов император падает в банду. Поражение — круг
    остаётся кругом (теряет только погибших). НЕ коммитит."""
    camps, m = await throne_context(session, contender_id, holder_id)
    result = simulate_battle(camps[contender_id], camps[holder_id], attacker_chances=m.attacker, defender_chances=m.defender)
    return await settle_liberation(session, contender_id, holder_id, country_code, camps, m, result)


async def settle_liberation(session: AsyncSession, contender_id: int, holder_id: int, country_code: str, camps, m, result) -> LiberationOutcome:
    """Последствия боя за освобождение (общие для онлайн-боя и мгновенного расчёта). НЕ коммитит."""
    await apply_losses(session, contender_id, CAMP_ATTACK, result.attacker.dead)
    abs_lines = await after_battle(session, m, result, kind=BATTLE_THRONE, attacker_id=contender_id, attacker_stacks=camps[contender_id], defender_id=holder_id)
    await apply_losses(session, holder_id, CAMP_DEFENSE, result.defender.dead)
    contender_gang, holder_gang = await get_gang(session, contender_id), await get_gang(session, holder_id)
    labels = {"contender_label": contender_gang.name if contender_gang else "—", "holder_label": holder_gang.name if holder_gang else "—"}
    won = result.attacker_won
    names: tuple[str, ...] = ()
    treasury = businesses = 0
    demoted = False
    if won:
        await accrue_many(session, [contender_id, holder_id])
        cities_before = await phase_repo.count_cities_of(session, holder_id)
        released = await phase_repo.release_cities(session, country_code, holder_id)
        names = tuple(n for _, n in released)
        ratio = result.attacker.initial_power / result.defender.initial_power if result.defender.initial_power else 10.0
        coins = await empire_repo.emperor_coins(session, holder_id, for_update=True)
        treasury = max(coins, 0) * war_treasury_percent(ratio) // 100
        if treasury:
            await empire_repo.move_coins(session, holder_id, contender_id, treasury, REASON_WAR_TREASURY)
        final = await phase_repo.count_cities_of(session, holder_id) == 0
        businesses = await phase_repo.transfer_holdings(
            session, holder_id, contender_id, [cid for cid, _ in released], cities_before, everything=final
        )
        if final:
            await demote_to_gang(session, holder_id)
            demoted = True
    await log_activity(session, contender_id, ACT_BATTLE, LOG_LIBERATION_CONTENDER.format(holder=labels["holder_label"], outcome=WON if won else LOST))
    await log_activity(session, holder_id, ACT_BATTLE, LOG_LIBERATION_HOLDER.format(contender=labels["contender_label"], outcome=LOST if won else WON))
    await remember_opponents(session, contender_id, holder_id)
    if won:
        await quest_event(session, contender_id, TASK_WIN_PVP)
    return LiberationOutcome(
        journal=journal(result, m.spy) + abs_lines, defender_journal=journal(result, m.spy, viewer_is_attacker=False) + abs_lines,
        contender_id=contender_id, holder_id=holder_id, contender_won=won, rounds=result.rounds,
        contender_dead=result.attacker.total_dead, holder_dead=result.defender.total_dead,
        city_names=names, treasury=treasury, businesses=businesses, holder_demoted=demoted, **labels,
    )


async def promote_or_throne(
    session: AsyncSession, user_id: int, city_id: int
) -> tuple[str | None, ThroneOutcome | None, tuple[LiberationOutcome, ...]]:
    """Проверка перехода фазы после захвата. Страна взята, но её города держат чужие императоры —
    бои за освобождение с каждым по очереди (проиграл один — дальше не идёт, остаётся кругом);
    все выиграны — как обычно: бой за трон, если трон своей страны занят, иначе коронация.
    → (новая фаза или None, итог боя за трон или None, бои за освобождение). НЕ коммитит."""
    promotion = await check_promotion(session, user_id, city_id)
    if promotion.foreign_holders or promotion.throne_incumbent is not None:
        # 2026-11-23: бои за освобождение и трон — только онлайн, по кнопке «👑 Бой за трон» (по очереди,
        # `services/arena.start_throne`); здесь — лишь подсказка, что очередь открыта.
        from bot.services.arena.scenarios import _notify
        from bot.texts.map import THRONE_READY_PUSH

        await _notify(user_id, THRONE_READY_PUSH)
        return None, None, ()
    return promotion.phase, None, ()


# ---------------------------------------------------------------- вызов на трон вручную (2026-10-20)
# Бой за трон и освобождение раньше шли ТОЛЬКО в момент захвата, закрывшего страну. Проиграл этот
# бой (или страна закрылась раньше) — круг застревал: все районы его, атаковать некого, повторить
# нечем (жалоба: «как я должен императора завалить, если я его не могу атаковать»). Теперь круг,
# держащий все районы страны, сам вызывает: сначала чужих держателей по очереди, потом трон.

class NotThroneContenderError(Exception):
    """Вызывать может только круг, держащий все районы своей страны."""

    def __init__(self, missing: int = 0) -> None:
        self.missing = missing  # районов страны ещё не его


class NoThroneTargetError(Exception):
    """Страна и так свободна — вызывать некого (коронация пройдёт на ближайшем захвате)."""


@dataclass(frozen=True, slots=True)
class ThroneOpponent:
    user_id: int
    label: str  # название банды
    is_throne: bool  # True — бой за трон с местным императором; False — освобождение у чужого
    cities: int  # сколько городов этой страны держит (для освобождения)


@dataclass(frozen=True, slots=True)
class ThroneStatus:
    can_challenge: bool
    missing: int  # районов страны ещё не у игрока (для подсказки)
    incumbent_id: int | None
    foreign_holders: tuple[int, ...]
    # Очередь боёв по кнопке — в том же порядке, что `promote_or_throne` (баг 2026-10-28: кнопка
    # не говорила, с кем бой, игроки дрались с чужим императором, думая, что с местным).
    queue: tuple[ThroneOpponent, ...] = ()


async def throne_status(session: AsyncSession, user_id: int) -> ThroneStatus:
    from bot.constant.phase import PHASE_CIRCLE

    phase, country = await phase_repo.get_phase(session, user_id)
    if phase != PHASE_CIRCLE or country is None:
        return ThroneStatus(False, 0, None, ())
    missing = int(await phase_repo.count_not_owned_in_country(session, country, user_id) or 0)
    holder_rows = await phase_repo.foreign_holders(session, country)
    holders = tuple(uid for uid, _ in holder_rows)
    incumbent = await phase_repo.country_emperor(session, country, exclude_user_id=user_id)

    async def label(uid: int) -> str:
        gang = await get_gang(session, uid)
        return gang.name if gang else "—"

    queue = [ThroneOpponent(uid, await label(uid), False, n) for uid, n in holder_rows]
    if incumbent is not None:
        queue.append(ThroneOpponent(incumbent, await label(incumbent), True, 0))
    return ThroneStatus(missing == 0 and bool(holders or incumbent), missing, incumbent, holders, tuple(queue))


async def challenge_throne(session: AsyncSession, redis, user_id: int):
    """Вызов на трон (и бои за освобождение) по кнопке. КД — как у боя круга. Коммитит.
    → (новая фаза или None, итог трона или None, бои за освобождение)."""
    from bot.cache.keys import battle_cooldown
    from bot.constant.cooldown import CD_BATTLE
    from bot.constant.phase import PHASE_CIRCLE
    from bot.db.models.user import User
    from bot.services.country import ensure_battles_open_for

    await ensure_battles_open_for(session, user_id)
    from bot.services.admin.live_config import battle_cooldown_seconds
    from bot.services.cooldown import schedule as schedule_ready
    from bot.services.district.district import BattleOnCooldownError

    status = await throne_status(session, user_id)
    if not status.can_challenge:
        if status.missing:
            raise NotThroneContenderError(status.missing)
        phase = (await phase_repo.get_phase(session, user_id))[0]
        if phase != PHASE_CIRCLE:
            raise NotThroneContenderError
        raise NoThroneTargetError
    key = battle_cooldown(user_id)
    profile = await get_combat_profile(session, user_id)
    if not await redis.set(key, "1", nx=True, ex=profile.cooldown(battle_cooldown_seconds(PHASE_CIRCLE), profile.eco.battle_cooldown)):
        raise BattleOnCooldownError(retry_after_seconds=max(0, await redis.ttl(key)))
    city_id = await session.scalar(select(User.city_id).where(User.id == user_id))
    try:
        result = await promote_or_throne(session, user_id, city_id)
        await session.commit()
    except Exception:
        await session.rollback()
        await redis.delete(key)
        raise
    await schedule_ready(redis, user_id, CD_BATTLE, await redis.ttl(key))
    return result
