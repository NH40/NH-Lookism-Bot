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
        redis, session=session, kind=KIND_DISTRICT, a_uid=user.id, d_uid=None, a_stacks=prep.stacks, d_stacks=prep.defender,
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


# --- PvP: вызов за район / город, защитник принял (2026-11-19) ---

KIND_CHALLENGE = "challenge"
_NOTIFY: dict[str, object] = {}


def set_notifier(fn) -> None:
    """`fn(user_id, text, battle_id)` — пуш (бот или API подставляют свой способ отправки); с `battle_id` — кнопка «Войти в бой»."""
    _NOTIFY["fn"] = fn


async def _notify(user_id: int | None, text: str, battle_id: str | None = None) -> None:
    fn = _NOTIFY.get("fn")
    if fn is not None and user_id:
        try:
            await fn(user_id, text, battle_id)
        except Exception:  # noqa: BLE001 — пуш не должен ломать итог боя
            pass


async def start_challenge(session: AsyncSession, redis: Redis, defender, challenge_id: int):
    """Защитник принимает вызов онлайн. Просрочен — как раньше, автобой лагерем защиты (→ `ChallengeOutcome`).
    Иначе вызов берётся, бой идёт онлайн (→ состояние арены); нападающий не в сети — за него ходит автоатака."""
    from bot.constant.district import RESOLUTION_ACCEPTED
    from bot.db.repositories.district import challenge as challenge_repo
    from bot.services.arena.sources import energy_for, perks_for
    from bot.services.district.challenge import ChallengeFight, ChallengeNotFoundError, accept_challenge, challenge_context
    from datetime import datetime, timezone

    challenge = await challenge_repo.get(session, challenge_id)
    if challenge is None or challenge.defender_id != defender.id:
        raise ChallengeNotFoundError
    if datetime.now(timezone.utc) >= challenge.expires_at:
        return await accept_challenge(session, redis, defender, challenge_id)
    for uid in (challenge.attacker_id, challenge.defender_id):
        if await core.current_of(redis, uid):
            raise core.ArenaError("in_battle")
    claimed = await challenge_repo.claim(session, challenge_id, RESOLUTION_ACCEPTED)
    if claimed is None:
        raise ChallengeNotFoundError
    ctx = await challenge_context(session, claimed, RESOLUTION_ACCEPTED)
    if not isinstance(ctx, ChallengeFight):
        return ctx  # аннулирован — защитнику уже нечего терять
    a_id, d_id = claimed.attacker_id, claimed.defender_id
    st = await core.create(
        redis, session=session, kind=KIND_CHALLENGE, a_uid=a_id, d_uid=d_id, a_stacks=ctx.stacks_a, d_stacks=ctx.stacks_d,
        a_chances=ctx.m.attacker, d_chances=ctx.m.defender, a_perks=await perks_for(session, a_id), d_perks=await perks_for(session, d_id),
        a_auto=False, d_auto=False, a_name=ctx.base["attacker_label"], d_name=ctx.base["defender_label"],
        meta={"challenge_id": challenge_id}, a_energy=await energy_for(session, a_id), d_energy=await energy_for(session, d_id),
    )
    await session.commit()  # вызов взят; блокировки стопок отпущены — бой идёт без транзакции
    await _notify(a_id, f"⚔️ <b>{ctx.base['defender_label']} принял твой вызов — бой начался!</b>\n\n"
                        "Жми «Войти в бой»: раунд 30 секунд, атака, защита, перки и мини-игры 🎮. "
                        "Не зайдёшь — за тебя ходит автоатака.", st["id"])
    return st


async def start_challenge_expired(session: AsyncSession, redis: Redis, challenge_id: int):
    """Защитник не ответил — бой всё равно онлайн (2026-11-20): нападающий ходит сам, за защитника автоатака лагерем
    защиты (может зайти и выключить её). None — нельзя (кто-то уже в бою) → прежний автобой; иначе состояние/итог."""
    from bot.constant.district import RESOLUTION_TIMEOUT
    from bot.db.repositories.district import challenge as challenge_repo
    from bot.services.arena.sources import energy_for, perks_for
    from bot.services.district.challenge import ChallengeFight, challenge_context

    challenge = await challenge_repo.get(session, challenge_id)
    if challenge is None:
        return None
    for uid in (challenge.attacker_id, challenge.defender_id):
        if await core.current_of(redis, uid):
            return None
    claimed = await challenge_repo.claim(session, challenge_id, RESOLUTION_TIMEOUT)
    if claimed is None:
        return None
    ctx = await challenge_context(session, claimed, RESOLUTION_TIMEOUT)
    if not isinstance(ctx, ChallengeFight):
        return ctx  # аннулирован или без боя — итог как раньше
    a_id, d_id = claimed.attacker_id, claimed.defender_id
    st = await core.create(
        redis, session=session, kind=KIND_CHALLENGE, a_uid=a_id, d_uid=d_id, a_stacks=ctx.stacks_a, d_stacks=ctx.stacks_d,
        a_chances=ctx.m.attacker, d_chances=ctx.m.defender, a_perks=await perks_for(session, a_id), d_perks=await perks_for(session, d_id),
        a_auto=False, d_auto=True, a_name=ctx.base["attacker_label"], d_name=f"{ctx.base['defender_label']} (оборона)",
        meta={"challenge_id": challenge_id, "resolution": RESOLUTION_TIMEOUT},
        a_energy=await energy_for(session, a_id), d_energy=await energy_for(session, d_id),
    )
    await session.commit()
    await _notify(a_id, f"⚔️ <b>{ctx.base['defender_label']} не ответил — бой с его обороной идёт онлайн!</b>\n\n"
                        "Жми «Войти в бой». Не зайдёшь — за тебя ходит автоатака.", st["id"])
    await _notify(d_id, f"🚨 <b>{ctx.base['attacker_label']} атакует твои земли!</b> Ты не принял вызов — бьётся лагерь защиты на автоатаке.\n\n"
                        "Зайди в бой и веди его сам: перки, мини-игры.", st["id"])
    return st


async def _finish_challenge(redis: Redis, st: dict, result) -> None:
    from bot.constant.district import RESOLUTION_ACCEPTED
    from bot.db.repositories.district import challenge as challenge_repo
    from bot.services.district.challenge import ChallengeFight, challenge_context, settle_challenge

    async with _SF["sf"]() as session:
        challenge = await challenge_repo.get(session, st["meta"]["challenge_id"])
        ctx = await challenge_context(session, challenge, st["meta"].get("resolution") or RESOLUTION_ACCEPTED)
        outcome = ctx if not isinstance(ctx, ChallengeFight) else await settle_challenge(session, redis, ctx, result)
    won = bool(outcome.attacker_won)
    st["report"] = {"won": won, "captured": outcome.captured, "districts": getattr(outcome, "captured_districts", 0)}
    await core.save(redis, st)
    a_text = f"🏁 Бой с {outcome.defender_label}: {'победа' if won else 'поражение'}" + (f", захвачено районов: {outcome.captured_districts}" if won and outcome.captured else "")
    d_text = f"🏁 Бой с {outcome.attacker_label}: {'поражение' if won else 'победа'}" + (f", потеряно районов: {outcome.captured_districts}" if won and outcome.captured else "")
    await _notify(st["a"]["uid"], a_text)
    await _notify(st["d"]["uid"], d_text)


core.register_finisher(KIND_CHALLENGE, _finish_challenge)


# --- трон и освобождение страны — по кнопке, по очереди (2026-11-23) ---

KIND_THRONE, KIND_LIBERATION = "throne", "liberation"


async def start_throne(session: AsyncSession, redis: Redis, user_id: int) -> dict:
    """Следующий бой очереди (чужие держатели, потом трон) — онлайн. Проверки и КД — как у прежнего
    `challenge_throne`; противник не в сети — за него автобой лагерем защиты, может зайти и вести сам."""
    from bot.cache.keys import battle_cooldown
    from bot.constant.cooldown import CD_BATTLE
    from bot.constant.phase import PHASE_CIRCLE
    from bot.db.repositories import phase as phase_repo
    from bot.services.admin.live_config import battle_cooldown_seconds
    from bot.services.arena.sources import energy_for, perks_for
    from bot.services.characteristic import get_combat_profile
    from bot.services.cooldown import schedule as schedule_ready
    from bot.services.country import ensure_battles_open_for
    from bot.services.district.district import BattleOnCooldownError
    from bot.services.district.throne import NoThroneTargetError, NotThroneContenderError, throne_context, throne_status

    await ensure_battles_open_for(session, user_id)
    status = await throne_status(session, user_id)
    if not status.can_challenge:
        if status.missing:
            raise NotThroneContenderError(status.missing)
        if (await phase_repo.get_phase(session, user_id))[0] != PHASE_CIRCLE:
            raise NotThroneContenderError
        raise NoThroneTargetError
    opp = status.queue[0]
    for uid in (user_id, opp.user_id):
        if await core.current_of(redis, uid):
            raise core.ArenaError("in_battle")
    key = battle_cooldown(user_id)
    profile = await get_combat_profile(session, user_id)
    if not await redis.set(key, "1", nx=True, ex=profile.cooldown(battle_cooldown_seconds(PHASE_CIRCLE), profile.eco.battle_cooldown)):
        raise BattleOnCooldownError(retry_after_seconds=max(0, await redis.ttl(key)))
    try:
        camps, m = await throne_context(session, user_id, opp.user_id)
        country = (await phase_repo.get_phase(session, user_id))[1]
        kind = KIND_THRONE if opp.is_throne else KIND_LIBERATION
        st = await core.create(
            redis, session=session, kind=kind, a_uid=user_id, d_uid=opp.user_id, a_stacks=camps[user_id], d_stacks=camps[opp.user_id],
            a_chances=m.attacker, d_chances=m.defender, a_perks=await perks_for(session, user_id), d_perks=await perks_for(session, opp.user_id),
            a_auto=False, d_auto=True, a_name=await _name(session, user_id), d_name=f"{opp.label} (оборона)",
            meta={"opp": opp.user_id, "country": country}, a_energy=await energy_for(session, user_id),
            d_energy=await energy_for(session, opp.user_id),
        )
    except Exception:
        await redis.delete(key)
        raise
    finally:
        await session.rollback()  # снять FOR UPDATE со стопок — бой идёт без транзакции
    await schedule_ready(redis, user_id, CD_BATTLE, await redis.ttl(key))
    title = "бой за трон" if opp.is_throne else "бой за освобождение страны"
    await _notify(opp.user_id, f"🚨 <b>{st['a']['name']} начал {title} с тобой!</b> Бьётся лагерь защиты на автоатаке — "
                               "зайди в бой и веди его сам.", st["id"])
    return st


async def _finish_throne(redis: Redis, st: dict, result) -> None:
    from bot.services.district.throne import settle_liberation, settle_throne, throne_context, throne_status

    a_id, opp = st["a"]["uid"], st["meta"]["opp"]
    async with _SF["sf"]() as session:
        camps, m = await throne_context(session, a_id, opp)
        if st["kind"] == KIND_THRONE:
            o = await settle_throne(session, a_id, opp, camps, m, result)
            text = (f"👑 Бой за трон с «{o.incumbent_label}»: победа — ты император страны!" if o.contender_won
                    else f"👑 Бой за трон с «{o.incumbent_label}»: поражение.")
            foe_text = (f"👑 «{o.contender_label}» взял твой трон." if o.contender_won else f"👑 Трон устоял: «{o.contender_label}» отбит.")
        else:
            o = await settle_liberation(session, a_id, opp, st["meta"]["country"], camps, m, result)
            text = (f"🏴 Освобождение у «{o.holder_label}»: победа, городов возвращено {len(o.city_names)}." if o.contender_won
                    else f"🏴 Освобождение у «{o.holder_label}»: поражение — ты остаёшься кругом.")
            foe_text = (f"🏴 «{o.contender_label}» освободил города своей страны." if o.contender_won
                        else f"🏴 «{o.contender_label}» не смог освободить страну — города твои.")
        await session.commit()
        more = (await throne_status(session, a_id)).can_challenge
    won = bool(o.contender_won)
    st["report"] = {"won": won}
    await core.save(redis, st)
    if won and more:
        text += " Следующий бой очереди — «👑 Бой за трон»."
    await _notify(a_id, "🏁 " + text)
    await _notify(opp, "🏁 " + foe_text)


core.register_finisher(KIND_THRONE, _finish_throne)


# --- клановая война за земли (2026-11-23) ---

KIND_CLAN_WAR = "clan_war"


async def start_clan_war(session: AsyncSession, redis: Redis, user_id: int, target_id: int):
    """Атака клана онлайн: бьётся нажавший (свои перки), рота защитника — на автобое. Пустая рота защитника —
    сдача без боя (→ `WarOutcome` сразу)."""
    from bot.services.arena.sources import energy_for, perks_for
    from bot.services.clan.war import WarBattle, start_attack

    if await core.current_of(redis, user_id):
        raise core.ArenaError("in_battle")
    b = await start_attack(session, redis, user_id, target_id)
    if not isinstance(b, WarBattle):
        return b
    st = await core.create(
        redis, session=session, kind=KIND_CLAN_WAR, a_uid=user_id, d_uid=None, a_stacks=b.a_stacks, d_stacks=b.d_stacks,
        a_chances=b.a_chances, d_chances=b.d_chances, a_perks=await perks_for(session, user_id), d_perks=[],
        a_auto=False, d_auto=True, a_name=f"Рота «{b.attacker_name}»", d_name=f"Рота «{b.defender_name}»",
        meta={"attacker": b.attacker_id, "defender": b.defender_id}, a_energy=await energy_for(session, user_id),
    )
    return st


async def _finish_clan_war(redis: Redis, st: dict, result) -> None:
    from bot.constant.settings import NOTIFY_CLAN_WAR
    from bot.handlers.clan.garrison import war_result_text
    from bot.services.clan.war import finish_attack
    from bot.services.settings import is_muted

    uid = st["a"]["uid"]
    async with _SF["sf"]() as session:
        out = await finish_attack(session, uid, st["meta"]["attacker"], st["meta"]["defender"], result)
        st["report"] = {"won": bool(out and out.attacker_won)}
        await core.save(redis, st)
        if out is None:
            await _notify(uid, "🏁 Клановая война: клан исчез за время боя — итог не засчитан.")
            return
        text = war_result_text(out)
        await _notify(uid, text)
        for member in {*out.attacker_members, *out.defender_members} - {uid}:
            if not await is_muted(session, member, NOTIFY_CLAN_WAR):
                await _notify(member, text)


core.register_finisher(KIND_CLAN_WAR, _finish_clan_war)
core.register_finisher(KIND_LIBERATION, _finish_throne)
