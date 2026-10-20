"""Кланы — казна, земли, здания, магазин клана, обменник (сервис). Дизайн — `docs/design/clans.md`.

Казну пополняют участники; тратят владелец и заместитель. Все списания — условные UPDATE
(правило 1), лок на клик (правило 2), один commit (правило 10). Каждое действие пишется в
журнал клана.
"""
from __future__ import annotations

from bot.constant.dev_quest import TASK_CLAN_DONATE

from bot.services.dev_quest import emit as quest_event

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import action_lock
from bot.config.characteristic import extra_power_for_rank
from bot.config.clan import (
    CLAN_BUILDINGS,
    CLAN_BUY_LANDS_MAX,
    CLAN_DEMOLISH_REFUND,
    CLAN_LANDS_PER_DONATE_LEVEL,
    CLAN_CONTRACT_COINS_PER_POWER,
    CLAN_CONTRACT_HOURS,
    CLAN_SHOP_POTION_TIERS,
    CLAN_SHOP_TICKET_PRICE,
    CLAN_SHOP_TICKETS_MAX,
    building_price,
    land_price,
)
from bot.config.game import ACTION_LOCK_MS
from bot.config.potion import POTION_EFFECTS, POTION_PRICES
from bot.constant.clan import BUILDINGS, LOCK_ACTION_CLAN, MANAGER_RANKS
from bot.constant.characteristic import RANK_INDEX
from bot.constant.potion import POTION_WEALTH, POTIONS
from bot.constant.resource import RES_COINS, RES_TICKETS, RESOURCES
from bot.db.models.clan import Clan
from bot.db.repositories import business as business_repo
from bot.db.repositories import clan as clan_repo
from bot.db.repositories import contract as contract_repo
from bot.db.repositories import potion as potion_repo
from bot.services.clan.clan import ClanError, require_member
from bot.services.resource import grant, spend
from bot.texts.clan import BUILDING_NAMES
from bot.texts.potion import POTION_NAMES
from bot.texts.resource import amount_label


def max_lands(clan: Clan) -> int:
    return CLAN_BUY_LANDS_MAX + CLAN_LANDS_PER_DONATE_LEVEL * clan.donate_level


@dataclass(frozen=True, slots=True)
class LandsView:
    clan: Clan
    buildings: dict[str, int]
    used: int
    max_lands: int
    next_land_price: int | None


async def _lock(redis: Redis, user_id: int) -> str:
    key = action_lock(user_id, LOCK_ACTION_CLAN)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise ClanError("busy")
    return key


async def _name(session: AsyncSession, user_id: int) -> str:
    return (await clan_repo.member_labels(session, [user_id])).get(user_id, ("—", None))[0]


async def lands_view(session: AsyncSession, user_id: int) -> LandsView:
    member = await require_member(session, user_id)
    clan = await clan_repo.get(session, member.clan_id)
    built = await clan_repo.buildings(session, clan.id)
    cap = max_lands(clan)
    return LandsView(clan, built, sum(built.values()), cap, land_price(clan.lands) if clan.lands < cap else None)


async def donate(session: AsyncSession, redis: Redis, user_id: int, amount: int) -> int:
    """Внести NHCoin в казну (любой участник). → новая казна."""
    if amount <= 0:
        raise ClanError("bad_amount")
    member = await require_member(session, user_id)
    key = await _lock(redis, user_id)
    try:
        if not await business_repo.spend_coins(session, user_id, amount):
            raise ClanError("no_coins", amount)
        await clan_repo.change_treasury(session, member.clan_id, amount)
        await clan_repo.bump_stats(session, member.clan_id, user_id, treasury=amount)
        await clan_repo.log(session, member.clan_id, f"💰 {await _name(session, user_id)} внёс(ла) в казну {amount_label(RES_COINS, amount)}")
        await quest_event(session, user_id, TASK_CLAN_DONATE)
        await session.commit()
        return (await clan_repo.get(session, member.clan_id)).treasury
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def buy_land(session: AsyncSession, redis: Redis, user_id: int) -> int:
    """Освоить землю за казну (владелец/зам). → земель теперь."""
    member = await require_member(session, user_id, MANAGER_RANKS)
    key = await _lock(redis, user_id)
    try:
        clan = await clan_repo.get(session, member.clan_id, for_update=True)
        if clan.lands >= max_lands(clan):
            raise ClanError("lands_max", max_lands(clan))
        price = land_price(clan.lands)
        if not await clan_repo.change_treasury(session, clan.id, -price):
            raise ClanError("no_treasury", price)
        await clan_repo.bump_stats(session, clan.id, user_id, build_spent=price)
        clan.lands += 1
        await clan_repo.log(session, clan.id, f"🌍 {await _name(session, user_id)} освоил(а) землю ({clan.lands}) за {amount_label(RES_COINS, price)}")
        lands = clan.lands
        await session.commit()
        return lands
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def build(session: AsyncSession, redis: Redis, user_id: int, kind: str) -> int:
    """Построить здание на свободной земле (владелец/зам). → сколько таких теперь."""
    if kind not in BUILDINGS:
        raise ClanError("bad_building")
    member = await require_member(session, user_id, MANAGER_RANKS)
    key = await _lock(redis, user_id)
    try:
        clan = await clan_repo.get(session, member.clan_id, for_update=True)
        built = await clan_repo.buildings(session, clan.id)
        if sum(built.values()) >= clan.lands:
            raise ClanError("no_free_land")
        have = built.get(kind, 0)
        if have >= CLAN_BUILDINGS[kind][0]:
            raise ClanError("building_max", CLAN_BUILDINGS[kind][0])
        price = building_price(kind, have)
        if not await clan_repo.change_treasury(session, clan.id, -price):
            raise ClanError("no_treasury", price)
        await clan_repo.bump_stats(session, clan.id, user_id, build_spent=price)
        await clan_repo.add_building(session, clan.id, kind, 1)
        await clan_repo.log(session, clan.id, f"🏗 {await _name(session, user_id)} построил(а) {BUILDING_NAMES[kind]} за {amount_label(RES_COINS, price)}")
        await session.commit()
        return have + 1
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def demolish(session: AsyncSession, redis: Redis, user_id: int, kind: str) -> int:
    """Снести одно здание: половина цены последнего — в казну. → возврат."""
    if kind not in BUILDINGS:
        raise ClanError("bad_building")
    member = await require_member(session, user_id, MANAGER_RANKS)
    key = await _lock(redis, user_id)
    try:
        clan = await clan_repo.get(session, member.clan_id, for_update=True)
        have = (await clan_repo.buildings(session, clan.id)).get(kind, 0)
        if have <= 0:
            raise ClanError("no_building")
        refund = int(building_price(kind, have - 1) * CLAN_DEMOLISH_REFUND)
        await clan_repo.add_building(session, clan.id, kind, -1)
        await clan_repo.change_treasury(session, clan.id, refund)
        await clan_repo.log(session, clan.id, f"🧱 {await _name(session, user_id)} снёс(ла) {BUILDING_NAMES[kind]}")
        await session.commit()
        return refund
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def exchange(session: AsyncSession, redis: Redis, user_id: int, target_id: int, resource: str, amount: int) -> None:
    """Обменник (как в UAP): передать ресурс участнику своего клана."""
    if resource not in RESOURCES or amount <= 0:
        raise ClanError("bad_amount")
    member = await require_member(session, user_id)
    target = await clan_repo.get_member(session, target_id)
    if target is None or target.clan_id != member.clan_id or target_id == user_id:
        raise ClanError("target_gone")
    key = await _lock(redis, user_id)
    try:
        if not await spend(session, user_id, resource, amount):
            raise ClanError("not_enough")
        await grant(session, target_id, resource, amount)
        await clan_repo.bump_stats(session, member.clan_id, user_id, exchanges=1)
        await clan_repo.log(
            session, member.clan_id,
            f"🔄 {await _name(session, user_id)} → {await _name(session, target_id)}: {amount_label(resource, amount)}",
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


# --- магазин клана (из казны, для всех участников) ---

async def _pay(session: AsyncSession, clan_id: int, price: int, user_id: int | None = None) -> None:
    if not await clan_repo.change_treasury(session, clan_id, -price):
        raise ClanError("no_treasury", price)
    if user_id is not None:
        await clan_repo.bump_stats(session, clan_id, user_id, shop_spent=price)


def tickets_price(tickets: int, members: int) -> int:
    return tickets * CLAN_SHOP_TICKET_PRICE * members


def potion_price(tier: int, members: int) -> int:
    return POTION_PRICES[tier - 1] * members


def contract_unit_price(rank: str) -> int:
    return extra_power_for_rank(rank) * CLAN_CONTRACT_COINS_PER_POWER


async def shop_tickets(session: AsyncSession, redis: Redis, user_id: int, tickets: int) -> tuple[int, int]:
    """Тикеты каждому участнику. → (цена, участников)."""
    if not 1 <= tickets <= CLAN_SHOP_TICKETS_MAX:
        raise ClanError("bad_item")
    member = await require_member(session, user_id, MANAGER_RANKS)
    key = await _lock(redis, user_id)
    try:
        ids = await clan_repo.member_ids(session, member.clan_id)
        price = tickets_price(tickets, len(ids))
        await _pay(session, member.clan_id, price, user_id)
        for uid in sorted(ids):
            await grant(session, uid, RES_TICKETS, tickets)
        await clan_repo.log(session, member.clan_id, f"🛒 {await _name(session, user_id)}: всем по {tickets} 🎟 за {amount_label(RES_COINS, price)}")
        await session.commit()
        return price, len(ids)
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def shop_potion(session: AsyncSession, redis: Redis, user_id: int, kind: str, tier: int) -> tuple[int, int]:
    """Зелье всем участникам (без зелья богатства — у него окно ленивого дохода у каждого)."""
    if kind not in POTIONS or kind == POTION_WEALTH or tier not in CLAN_SHOP_POTION_TIERS:
        raise ClanError("bad_item")
    member = await require_member(session, user_id, MANAGER_RANKS)
    key = await _lock(redis, user_id)
    try:
        ids = await clan_repo.member_ids(session, member.clan_id)
        price = potion_price(tier, len(ids))
        await _pay(session, member.clan_id, price, user_id)
        now = datetime.now(timezone.utc)
        ends = now + timedelta(minutes=POTION_EFFECTS[kind][0])
        for uid in sorted(ids):
            await potion_repo.drink(session, uid, kind, tier, now, ends)
        await clan_repo.log(session, member.clan_id, f"🧪 {await _name(session, user_id)}: {POTION_NAMES[kind]} {tier} тира всем за {amount_label(RES_COINS, price)}")
        await session.commit()
        return price, len(ids)
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def shop_contracts(session: AsyncSession, redis: Redis, user_id: int, rank: str, quantity: int, ceiling: str) -> int:
    """Контрактники в роту на `CLAN_CONTRACT_HOURS` (не выше потолка влияния покупателя): воюют
    за роту, гибнут, по сроку уходят; забрать себе их не может никто. → цена."""
    if rank not in RANK_INDEX or RANK_INDEX[rank] > RANK_INDEX[ceiling] or quantity <= 0:
        raise ClanError("bad_item")
    member = await require_member(session, user_id, MANAGER_RANKS)
    key = await _lock(redis, user_id)
    try:
        price = contract_unit_price(rank) * quantity
        await _pay(session, member.clan_id, price, user_id)
        await contract_repo.create_clan(session, member.clan_id, rank, quantity, datetime.now(timezone.utc) + timedelta(hours=CLAN_CONTRACT_HOURS))
        await clan_repo.log(
            session, member.clan_id,
            f"📜 {await _name(session, user_id)}: контракт {quantity} × {rank} в роту на {CLAN_CONTRACT_HOURS} ч за {amount_label(RES_COINS, price)}",
        )
        await session.commit()
        return price
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def buy_donate_level(session: AsyncSession, redis: Redis, user_id: int) -> int:
    """Купить следующий донат-уровень клана за донат-коины (любой участник). Уровень привязан к
    купившему: ушёл из клана — уровень пропадает, уплаченное возвращается. Коммитит. → новый уровень."""
    from bot.config.clan import CLAN_DONATE_LEVELS, clan_donate_price
    from bot.db.repositories import donate as donate_repo

    member = await require_member(session, user_id)
    key = await _lock(redis, user_id)
    try:
        clan = await clan_repo.lock_clan(session, member.clan_id)
        if clan.donate_level >= len(CLAN_DONATE_LEVELS):
            raise ClanError("donate_max")
        price = clan_donate_price(clan.donate_level + 1)
        if not await donate_repo.spend(session, user_id, price):
            raise ClanError("no_donate", price)
        await clan_repo.add_donate_purchase(session, clan.id, user_id, price)
        await clan_repo.log(session, clan.id, f"💎 {await _name(session, user_id)} поднял(а) уровень клана до {clan.donate_level + 1}")
        await session.commit()
        return clan.donate_level + 1
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def refund_on_exit(session: AsyncSession, clan_id: int, user_id: int | None = None) -> list[tuple[int, int]]:
    """Игрок уходит из клана (или клан удаляют — `user_id=None`): его донат-уровни пропадают,
    уплаченное — обратно. НЕ коммитит (шаг выхода/кика/удаления)."""
    refunds = await clan_repo.refund_donate(session, clan_id, user_id)
    for uid, amount in refunds:
        if user_id is not None:
            await clan_repo.log(session, clan_id, f"💎 Уровни клана {await _name(session, uid)} ушли вместе с ним(ней) — возвращено {amount} 💎")
    return refunds


async def set_donate_level(session: AsyncSession, clan_id: int, level: int) -> None:
    """Донат-уровень клана (покупка — с доменом доната; пока — для админки и тестов). Коммитит."""
    from bot.config.clan import CLAN_DONATE_LEVELS

    await session.execute(update(Clan).where(Clan.id == clan_id).values(donate_level=max(0, min(level, len(CLAN_DONATE_LEVELS)))))
    await session.commit()
