"""Админка «Кланы» (сервис). Мутации пишут аудит в той же транзакции и коммитят один раз."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.clan import CLAN_BUY_LANDS_MAX, CLAN_DONATE_LEVELS, CLAN_LANDS_PER_DONATE_LEVEL, CLAN_MIN_LANDS
from bot.constant.admin.clans_admin import (
    AUDIT_C_COOLDOWN, AUDIT_C_DELETE, AUDIT_C_DONATE, AUDIT_C_LANDS, AUDIT_C_SHIELD, AUDIT_C_TRANSFER,
    AUDIT_C_TREASURY, SEARCH_LIMIT,
)
from bot.constant.clan import RANK_MEMBER, RANK_OWNER
from bot.db.models.clan import Clan
from bot.db.repositories import clan as clan_repo  # noqa: F401
from bot.services.admin import audit
from bot.services.clan.economy import refund_on_exit
from bot.services.clan.garrison import clan_power
from bot.services.clan.war import cooldown_left, shield_left

LANDS_MIN = CLAN_MIN_LANDS
LANDS_MAX = CLAN_BUY_LANDS_MAX + len(CLAN_DONATE_LEVELS) * CLAN_LANDS_PER_DONATE_LEVEL
DONATE_MAX = len(CLAN_DONATE_LEVELS)


@dataclass(frozen=True, slots=True)
class ClanCard:
    clan: Clan
    owner_label: str
    members: list[tuple[int, str, str]]  # (user_id, rank, label)
    buyers: int
    paid: int
    power: int
    shield: int
    cooldown: int


async def find(session: AsyncSession, query: str) -> list[Clan]:
    query = query.strip()
    if query.isdigit():
        clan = await clan_repo.get(session, int(query))
        if clan is not None:
            return [clan]
    rows = await session.scalars(
        select(Clan).where(func.lower(Clan.name).like(f"%{query.lower()}%")).order_by(Clan.name).limit(SEARCH_LIMIT)
    )
    return list(rows.all())


async def card(session: AsyncSession, clan_id: int) -> ClanCard | None:
    clan = await clan_repo.get(session, clan_id)
    if clan is None:
        return None
    members = list(await clan_repo.list_members(session, clan_id))
    labels = await clan_repo.member_labels(session, [m.user_id for m in members])
    buyers = await clan_repo.donate_buyers(session, clan_id)
    owner = labels.get(clan.owner_id, ("—", None))[0]
    return ClanCard(
        clan, owner, [(m.user_id, m.rank, labels.get(m.user_id, ("—", None))[0]) for m in members],
        len({u for u, _ in buyers}), sum(p for _, p in buyers), await clan_power(session, clan_id),
        shield_left(clan), cooldown_left(clan),
    )


async def transfer_owner(session: AsyncSession, admin_id: int, clan_id: int, user_id: int) -> bool:
    clan = await clan_repo.lock_clan(session, clan_id)
    target = await clan_repo.get_member(session, user_id)
    if clan is None or target is None or target.clan_id != clan_id or user_id == clan.owner_id:
        return False
    old = clan.owner_id
    # Сначала снять владельца — освобождает слот в уникальном индексе «один владелец на клан».
    await clan_repo.set_rank(session, old, RANK_MEMBER)
    await clan_repo.set_rank(session, user_id, RANK_OWNER)
    await clan_repo.set_owner(session, clan_id, user_id)
    await clan_repo.log(session, clan_id, "👑 Владение клана изменено администрацией")
    await audit.log(session, admin_id, AUDIT_C_TRANSFER, user_id, {"clan_id": clan_id, "old_owner": old})
    await session.commit()
    return True


async def set_lands(session: AsyncSession, admin_id: int, clan_id: int, lands: int) -> bool:
    if not LANDS_MIN <= lands <= LANDS_MAX:
        return False
    clan = await clan_repo.lock_clan(session, clan_id)
    if clan is None:
        return False
    old, clan.lands = clan.lands, lands
    await audit.log(session, admin_id, AUDIT_C_LANDS, None, {"clan_id": clan_id, "old": old, "new": lands})
    await session.commit()
    return True


async def change_treasury(session: AsyncSession, admin_id: int, clan_id: int, delta: int) -> int | None:
    """→ новая казна; None — клана нет или не хватает на списание (атомарно, правило 1)."""
    if not await clan_repo.change_treasury(session, clan_id, delta):
        await session.rollback()
        return None
    value = await session.scalar(select(Clan.treasury).where(Clan.id == clan_id))
    await audit.log(session, admin_id, AUDIT_C_TREASURY, None, {"clan_id": clan_id, "delta": delta})
    await session.commit()
    return int(value)


async def set_donate_level(session: AsyncSession, admin_id: int, clan_id: int, level: int) -> bool:
    """Та же логика, что `services.clan.set_donate_level` (запись только уровня, без строк покупок),
    но без собственного commit — чтобы аудит лёг в одну транзакцию с изменением."""
    if not 0 <= level <= DONATE_MAX:
        return False
    result = await session.execute(update(Clan).where(Clan.id == clan_id).values(donate_level=level))
    if not result.rowcount:
        return False
    await audit.log(session, admin_id, AUDIT_C_DONATE, None, {"clan_id": clan_id, "level": level})
    await session.commit()
    return True


async def remove_shield(session: AsyncSession, admin_id: int, clan_id: int) -> bool:
    """Щит и КД войны хранятся колонками `clans.shield_until` / `clans.last_attack_at` (не Redis)."""
    clan = await clan_repo.lock_clan(session, clan_id)
    if clan is None or shield_left(clan) == 0:
        return False
    clan.shield_until = None
    await audit.log(session, admin_id, AUDIT_C_SHIELD, None, {"clan_id": clan_id})
    await session.commit()
    return True


async def remove_cooldown(session: AsyncSession, admin_id: int, clan_id: int) -> bool:
    clan = await clan_repo.lock_clan(session, clan_id)
    if clan is None or cooldown_left(clan) == 0:
        return False
    clan.last_attack_at = None
    await audit.log(session, admin_id, AUDIT_C_COOLDOWN, None, {"clan_id": clan_id})
    await session.commit()
    return True


async def delete_clan(session: AsyncSession, admin_id: int, clan_id: int) -> tuple[str, list[int], int] | None:
    """Удалить клан с возвратом донат-покупателям. → (название, id участников, возвращено всего)."""
    clan = await clan_repo.lock_clan(session, clan_id)
    if clan is None:
        return None
    members = await clan_repo.member_ids(session, clan_id)
    refunds = await refund_on_exit(session, clan_id)
    total = sum(amount for _, amount in refunds)
    name, owner_id = clan.name, clan.owner_id
    await clan_repo.delete_clan(session, clan_id)
    await audit.log(
        session, admin_id, AUDIT_C_DELETE, owner_id,
        {"clan_id": clan_id, "name": name, "members": len(members), "refunded": total, "refunds": dict(refunds)},
    )
    await session.commit()
    return name, members, total
