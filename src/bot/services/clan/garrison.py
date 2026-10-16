"""Кланы — клановая рота (сервис). Отдельная механика клана, не здание (уточнение пользователя
2026-10-04): участники вносят статистов и уников, любой участник может забрать их себе, а
мощь клана и войны за земли считаются по роте.

Забрать бойцов (пользователь 2026-10-04): всем — не раньше суток в клане; рядовому участнику в
первый раз — с одобрения владельца или заместителя (запрос → одобрили/отказали); одобрили один
раз — дальше без подтверждения. Капитан и старше — без одобрения.

Внести — забрать бойцов из своих лагерей (защита, потом атака) под `FOR UPDATE`; забрать —
условный UPDATE роты (двойной клик и двое участников не заберут одних и тех же бойцов
дважды), бойцы встают в лагерь защиты. Забирать можно через сутки после вступления —
защита от «вступил, забрал всё, ушёл». Каждое движение — в журнал клана.
"""
from __future__ import annotations

from bot.constant.dev_quest import TASK_GARRISON

from bot.services.dev_quest import emit as quest_event

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.card import CARD_BY_CODE
from bot.config.characteristic import extra_unit_power, statist_unit_power
from bot.config.clan import CLAN_GARRISON_TENURE_HOURS
from bot.config.school import (
    SCHOOL_BLOCK_PER_LEVEL,
    SCHOOL_COUNTER_PER_LEVEL,
    SCHOOL_DODGE_PER_LEVEL,
    SCHOOL_FLEE_PER_LEVEL,
)
from bot.constant.clan import GARRISON_FREE_RANKS
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
from bot.db.repositories import card as card_repo
from bot.db.repositories import clan as clan_repo
from bot.db.repositories import contract as contract_repo
from bot.services.clan.clan import ClanError, require_member
from bot.services.clan.economy import _lock, _name
from bot.services.combat import CombatStack
from bot.services.resource import StatistKey, give_statists, take_statists

KIND_STATIST = "x"
KIND_CARD = "u"
KIND_CONTRACT = "c"  # контрактники роты (`clan_contracts`) — забрать нельзя


@dataclass(frozen=True, slots=True)
class GarrisonView:
    statists: list[tuple[StatistKey, int, float]]  # ключ, сколько, мощь бойца
    cards: list[tuple[str, int, int]]  # код, сколько, мощь
    power: int
    can_take: bool
    take_in_seconds: int
    needs_approval: bool = False  # нет права забирать (выдаёт владелец)
    pending: bool = False  # запрос доступа ждёт ответа
    contracts: tuple = ()  # (ранг, сколько, мощь бойца, секунд до конца) — забрать нельзя


def _card_power(code: str) -> int:
    card = CARD_BY_CODE.get(code)
    return card.power if card else 0


def _key(row) -> StatistKey:
    return StatistKey(row.rank, row.stars, row.training_level, row.school, row.school_level)


async def garrison_stacks(session: AsyncSession, clan_id: int, *, for_update: bool = False) -> list[CombatStack]:
    """Рота клана как армия для боевого движка (школы дают стопкам свои реакции, как в лагерях)."""
    stacks = []
    for row in await clan_repo.garrison_extras(session, clan_id, for_update=for_update):
        level = row.school_level if row.school else 0
        stacks.append(CombatStack(
            key=(KIND_STATIST, row.rank, row.stars, row.training_level, row.school, row.school_level),
            unit_power=statist_unit_power(row.rank, row.stars, row.training_level, row.school, row.school_level),
            quantity=row.quantity,
            dodge=SCHOOL_DODGE_PER_LEVEL.get(row.school, 0.0) * level,
            block=SCHOOL_BLOCK_PER_LEVEL.get(row.school, 0.0) * level,
            counter=SCHOOL_COUNTER_PER_LEVEL.get(row.school, 0.0) * level,
            flee=SCHOOL_FLEE_PER_LEVEL.get(row.school, 0.0) * level,
        ))
    for row in await clan_repo.garrison_cards(session, clan_id, for_update=for_update):
        stacks.append(CombatStack(key=(KIND_CARD, row.card_code), unit_power=_card_power(row.card_code), quantity=row.quantity))
    for row in await contract_repo.list_clan_active(session, clan_id, for_update=for_update):
        stacks.append(CombatStack(key=(KIND_CONTRACT, row.id), unit_power=extra_unit_power(row.rank, 0, 0), quantity=row.quantity))
    return stacks


def stacks_power(stacks: list[CombatStack]) -> int:
    return round(sum(s.unit_power * s.quantity for s in stacks))


async def clan_power(session: AsyncSession, clan_id: int) -> int:
    """Мощь клана = мощь роты."""
    return stacks_power(await garrison_stacks(session, clan_id))


async def apply_losses(session: AsyncSession, clan_id: int, dead: dict) -> None:
    """Потери роты в войне. НЕ коммитит."""
    for key, count in dead.items():
        if count <= 0:
            continue
        if key[0] == KIND_CONTRACT:
            await contract_repo.lose_clan(session, key[1], count)
        elif key[0] == KIND_STATIST:
            _, rank, stars, level, school, school_level = key
            await clan_repo.add_garrison_extra(
                session, clan_id, {"rank": rank, "stars": stars, "training_level": level, "school": school, "school_level": school_level}, -count
            )
        else:
            await clan_repo.add_garrison_card(session, clan_id, key[1], -count)


async def view(session: AsyncSession, user_id: int) -> GarrisonView:
    member = await require_member(session, user_id)
    statists = [(_key(r), r.quantity, statist_unit_power(r.rank, r.stars, r.training_level, r.school, r.school_level))
                for r in await clan_repo.garrison_extras(session, member.clan_id)]
    cards = [(r.card_code, r.quantity, _card_power(r.card_code)) for r in await clan_repo.garrison_cards(session, member.clan_id)]
    now = datetime.now(timezone.utc)
    contracts = tuple(
        (r.rank, r.quantity, extra_unit_power(r.rank, 0, 0), max(0, int((r.expires_at - now).total_seconds())))
        for r in await contract_repo.list_clan_active(session, member.clan_id)
    )
    power = round(sum(q * p for _, q, p in statists) + sum(q * p for _, q, p in cards) + sum(q * p for _, q, p, _ in contracts))
    ready_at = member.joined_at + timedelta(hours=CLAN_GARRISON_TENURE_HOURS)
    left = max(0, int((ready_at - datetime.now(timezone.utc)).total_seconds()))
    return GarrisonView(
        statists, cards, power, left == 0, left, needs_approval(member), member.garrison_request_at is not None, contracts
    )


def needs_approval(member) -> bool:
    return member.rank not in GARRISON_FREE_RANKS and not member.garrison_approved


async def _take_cards(session: AsyncSession, user_id: int, code: str, amount: int) -> bool:
    """Забрать копии уника из армии игрока (защита, потом атака). НЕ коммитит."""
    stacks = []
    for camp in (CAMP_DEFENSE, CAMP_ATTACK):
        stack = await card_repo.get_stack_for_update(session, user_id=user_id, card_code=code, camp=camp)
        stacks.append((camp, stack.quantity if stack else 0))
    if sum(q for _, q in stacks) < amount:
        return False
    left = amount
    for camp, have in stacks:
        take = min(have, left)
        if take:
            await card_repo.add_to_stack(session, user_id=user_id, card_code=code, camp=camp, quantity=-take)
            left -= take
    return True


async def put_statists(session: AsyncSession, redis: Redis, user_id: int, key: StatistKey, amount: int) -> None:
    if amount <= 0:
        raise ClanError("bad_amount")
    member = await require_member(session, user_id)
    lock = await _lock(redis, user_id)
    try:
        if not await take_statists(session, user_id, key, amount):
            raise ClanError("not_enough")
        await clan_repo.add_garrison_extra(session, member.clan_id, key.stack(), amount)
        await clan_repo.log(session, member.clan_id, f"⚔️ {await _name(session, user_id)} внёс(ла) в роту {amount} × {key.rank}")
        await quest_event(session, user_id, TASK_GARRISON)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(lock)


async def put_cards(session: AsyncSession, redis: Redis, user_id: int, code: str, amount: int) -> None:
    if amount <= 0 or code not in CARD_BY_CODE:
        raise ClanError("bad_amount")
    member = await require_member(session, user_id)
    lock = await _lock(redis, user_id)
    try:
        if not await _take_cards(session, user_id, code, amount):
            raise ClanError("not_enough")
        await clan_repo.add_garrison_card(session, member.clan_id, code, amount)
        await clan_repo.log(session, member.clan_id, f"⚔️ {await _name(session, user_id)} внёс(ла) в роту уника {CARD_BY_CODE[code].name} ×{amount}")
        await quest_event(session, user_id, TASK_GARRISON)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(lock)


async def _check_tenure(member) -> None:
    """Можно ли забирать: сутки в клане и (для рядового) одобрение владельца или зама."""
    ready_at = member.joined_at + timedelta(hours=CLAN_GARRISON_TENURE_HOURS)
    left = int((ready_at - datetime.now(timezone.utc)).total_seconds())
    if left > 0:
        raise ClanError("tenure", left)
    if needs_approval(member):
        raise ClanError("approval_pending" if member.garrison_request_at else "needs_approval")


async def request_access(session: AsyncSession, user_id: int) -> int:
    """Рядовой просит доступ к роте. → id клана (для пушей владельцу и заму). Коммитит."""
    member = await require_member(session, user_id)
    if not needs_approval(member):
        raise ClanError("access_not_needed")
    if not await clan_repo.request_garrison_access(session, user_id):
        raise ClanError("approval_pending")
    await clan_repo.log(session, member.clan_id, f"🔑 {await _name(session, user_id)} просит доступ к роте")
    await session.commit()
    return member.clan_id


async def access_requests(session: AsyncSession, actor_id: int) -> list[tuple[int, str]]:
    """Ждущие запросы доступа к роте (видит владелец — только он выдаёт право)."""
    actor = await require_member(session, actor_id, GARRISON_FREE_RANKS)
    rows = await clan_repo.garrison_requests(session, actor.clan_id)
    labels = await clan_repo.member_labels(session, [m.user_id for m in rows])
    return [(m.user_id, labels[m.user_id][0]) for m in rows]


async def resolve_access(session: AsyncSession, actor_id: int, user_id: int, approved: bool) -> None:
    """Одобрить (пока владелец не отнимет) или отклонить запрос — только владелец. Коммитит."""
    actor = await require_member(session, actor_id, GARRISON_FREE_RANKS)
    if not await clan_repo.resolve_garrison_access(session, actor.clan_id, user_id, approved):
        raise ClanError("request_gone")
    verdict = "одобрил(а)" if approved else "отклонил(а)"
    await clan_repo.log(session, actor.clan_id, f"🔑 {await _name(session, actor_id)} {verdict} доступ к роте: {await _name(session, user_id)}")
    await session.commit()


async def access_list(session: AsyncSession, actor_id: int) -> list[tuple[int, str, bool, bool]]:
    """Участники (кроме владельца) для экрана доступа: (user_id, имя, есть право, просит доступ)."""
    actor = await require_member(session, actor_id, GARRISON_FREE_RANKS)
    members = [m for m in await clan_repo.list_members(session, actor.clan_id) if m.user_id != actor_id]
    labels = await clan_repo.member_labels(session, [m.user_id for m in members])
    return [(m.user_id, labels[m.user_id][0], m.garrison_approved, m.garrison_request_at is not None) for m in members]


async def set_access(session: AsyncSession, actor_id: int, user_id: int, allowed: bool) -> None:
    """Владелец выдаёт или отнимает у участника право забирать из роты (2026-10-12). Коммитит."""
    actor = await require_member(session, actor_id, GARRISON_FREE_RANKS)
    if user_id == actor_id or not await clan_repo.set_garrison_access(session, actor.clan_id, user_id, allowed):
        raise ClanError("not_member")
    verdict = "выдал(а)" if allowed else "отнял(а)"
    await clan_repo.log(session, actor.clan_id, f"🔑 {await _name(session, actor_id)} {verdict} доступ к роте: {await _name(session, user_id)}")
    await session.commit()


async def take_statists_from(session: AsyncSession, redis: Redis, user_id: int, key: StatistKey, amount: int) -> None:
    if amount <= 0:
        raise ClanError("bad_amount")
    member = await require_member(session, user_id)
    await _check_tenure(member)
    lock = await _lock(redis, user_id)
    try:
        if not await clan_repo.take_garrison_extra(session, member.clan_id, key.stack(), amount):
            raise ClanError("not_enough")
        await give_statists(session, user_id, key, amount)
        await clan_repo.log(session, member.clan_id, f"📤 {await _name(session, user_id)} забрал(а) из роты {amount} × {key.rank}")
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(lock)


async def take_cards_from(session: AsyncSession, redis: Redis, user_id: int, code: str, amount: int) -> None:
    if amount <= 0:
        raise ClanError("bad_amount")
    member = await require_member(session, user_id)
    await _check_tenure(member)
    lock = await _lock(redis, user_id)
    try:
        if not await clan_repo.take_garrison_card(session, member.clan_id, code, amount):
            raise ClanError("not_enough")
        await card_repo.add_to_stack(session, user_id=user_id, card_code=code, camp=CAMP_DEFENSE, quantity=amount)
        name = CARD_BY_CODE[code].name if code in CARD_BY_CODE else code
        await clan_repo.log(session, member.clan_id, f"📤 {await _name(session, user_id)} забрал(а) из роты уника {name} ×{amount}")
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(lock)
