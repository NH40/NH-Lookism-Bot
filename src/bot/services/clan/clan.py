"""Кланы — ядро (сервис): как в Universe Anime Planet (`services/clan` UAP), плюс создание за
NHCoin. Дизайн — `docs/design/clans.md`.

Ошибки — `ClanError(code)` с кодом текста (`texts/clan.ERRORS`). Составные операции — один
commit (правило 10); атомарность — insert ON CONFLICT, условные UPDATE и частичный уникальный
индекс «один владелец и один зам на клан».
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.clan import CLAN_CREATE_COST, CLAN_MAX_MEMBERS, CLAN_START_LANDS, CLAN_TOP_IMAGE
from bot.constant.clan import KICK_RANKS, MANAGER_RANKS, RANK_LEVEL, RANK_MEMBER, RANK_OWNER, RANKS
from bot.db.models.clan import Clan, ClanMember
from bot.db.repositories import business as business_repo
from bot.db.repositories import clan as clan_repo
from bot.db.repositories.user import find_by_username


class ClanError(Exception):
    def __init__(self, code: str, value: int | str = 0) -> None:
        super().__init__(code)
        self.code, self.value = code, value


@dataclass(frozen=True, slots=True)
class ClanView:
    clan: Clan
    members: int
    owner_label: str
    top10: bool


async def member_of(session: AsyncSession, user_id: int) -> ClanMember | None:
    return await clan_repo.get_member(session, user_id)


async def require_member(session: AsyncSession, user_id: int, ranks: tuple[str, ...] = RANKS) -> ClanMember:
    member = await clan_repo.get_member(session, user_id)
    if member is None:
        raise ClanError("not_in_clan")
    if member.rank not in ranks:
        raise ClanError("no_rights")
    return member


async def view(session: AsyncSession, clan_id: int) -> ClanView | None:
    clan = await clan_repo.get(session, clan_id)
    if clan is None:
        return None
    labels = await clan_repo.member_labels(session, [clan.owner_id])
    return ClanView(
        clan, await clan_repo.count_members(session, clan_id), labels.get(clan.owner_id, ("—", None))[0],
        clan_id in await clan_repo.top_ids(session, CLAN_TOP_IMAGE),
    )


async def create(session: AsyncSession, user_id: int, name: str) -> Clan:
    """Клан + владелец в участниках + списание NHCoin — одной транзакцией."""
    if await clan_repo.get_member(session, user_id):
        raise ClanError("already_in_clan")
    if not await business_repo.spend_coins(session, user_id, CLAN_CREATE_COST):
        raise ClanError("no_coins", CLAN_CREATE_COST)
    clan = await clan_repo.create(session, name=name, owner_id=user_id, lands=CLAN_START_LANDS)
    if clan is None:
        await session.rollback()
        raise ClanError("name_taken")
    if not await clan_repo.add_member(session, clan.id, user_id, RANK_OWNER):
        await session.rollback()
        raise ClanError("already_in_clan")
    await clan_repo.delete_requests_of(session, user_id)
    await clan_repo.log(session, clan.id, "🏰 Клан основан")
    await session.commit()
    return clan


async def browse(session: AsyncSession, page: int, page_size: int) -> tuple[list[tuple[Clan, int]], int, int]:
    total_pages = max(1, math.ceil(await clan_repo.count_clans(session) / page_size))
    page = max(0, min(page, total_pages - 1))
    return await clan_repo.top_page(session, page_size, page * page_size), page, total_pages


async def apply(session: AsyncSession, user_id: int, clan_id: int) -> None:
    """Заявка — максимум в один клан одновременно (как в UAP)."""
    if await clan_repo.get_member(session, user_id):
        raise ClanError("already_in_clan")
    if await clan_repo.get(session, clan_id) is None:
        raise ClanError("clan_gone")
    existing = await clan_repo.application_of(session, user_id)
    if existing is not None and existing.clan_id != clan_id:
        raise ClanError("applied_elsewhere")
    await clan_repo.create_request(session, clan_id, user_id, is_invite=False)
    await session.commit()


async def cancel_application(session: AsyncSession, user_id: int, clan_id: int) -> None:
    request = await clan_repo.get_request(session, clan_id, user_id)
    if request is not None and not request.is_invite:
        await clan_repo.delete_request(session, clan_id, user_id)
        await session.commit()


async def _join(session: AsyncSession, clan_id: int, user_id: int) -> None:
    if await clan_repo.count_members(session, clan_id) >= CLAN_MAX_MEMBERS:
        raise ClanError("clan_full", CLAN_MAX_MEMBERS)
    if not await clan_repo.add_member(session, clan_id, user_id, RANK_MEMBER):
        raise ClanError("already_in_clan")
    await clan_repo.delete_requests_of(session, user_id)
    labels = await clan_repo.member_labels(session, [user_id])
    await clan_repo.log(session, clan_id, f"➕ {labels[user_id][0]} вступил(а) в клан")
    await session.commit()


async def accept(session: AsyncSession, actor_id: int, user_id: int) -> int:
    """Принять заявку (владелец/зам). → id клана."""
    actor = await require_member(session, actor_id, MANAGER_RANKS)
    request = await clan_repo.get_request(session, actor.clan_id, user_id)
    if request is None or request.is_invite:
        raise ClanError("request_gone")
    await _join(session, actor.clan_id, user_id)
    return actor.clan_id


async def reject(session: AsyncSession, actor_id: int, user_id: int) -> None:
    actor = await require_member(session, actor_id, MANAGER_RANKS)
    await clan_repo.delete_request(session, actor.clan_id, user_id)
    await session.commit()


async def invite(session: AsyncSession, actor_id: int, username: str) -> tuple[int, int]:
    """Пригласить по юзернейму (владелец/зам). → (id приглашённого, id клана)."""
    actor = await require_member(session, actor_id, MANAGER_RANKS)
    target = await find_by_username(session, username.lstrip("@"))
    if target is None or target.city_id is None:
        raise ClanError("no_player")
    if await clan_repo.get_member(session, target.id):
        raise ClanError("target_in_clan")
    await clan_repo.create_request(session, actor.clan_id, target.id, is_invite=True)
    await session.commit()
    return target.id, actor.clan_id


async def accept_invite(session: AsyncSession, user_id: int, clan_id: int) -> None:
    request = await clan_repo.get_request(session, clan_id, user_id)
    if request is None or not request.is_invite:
        raise ClanError("request_gone")
    await _join(session, clan_id, user_id)


async def decline_invite(session: AsyncSession, user_id: int, clan_id: int) -> None:
    await clan_repo.delete_request(session, clan_id, user_id)
    await session.commit()


async def set_rank(session: AsyncSession, actor_id: int, user_id: int, rank: str) -> None:
    """Ранги раздаёт владелец; владелец меняется только передачей клана."""
    actor = await require_member(session, actor_id, (RANK_OWNER,))
    if rank not in RANKS or rank == RANK_OWNER:
        raise ClanError("no_rights")
    target = await clan_repo.get_member(session, user_id)
    if target is None or target.clan_id != actor.clan_id or target.rank == RANK_OWNER:
        raise ClanError("not_member")
    try:
        await clan_repo.set_rank(session, user_id, rank)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ClanError("deputy_taken") from None


async def transfer(session: AsyncSession, actor_id: int, user_id: int) -> None:
    actor = await require_member(session, actor_id, (RANK_OWNER,))
    target = await clan_repo.get_member(session, user_id)
    if target is None or target.clan_id != actor.clan_id or user_id == actor_id:
        raise ClanError("not_member")
    # Сначала снять владельца — освобождает слот в уникальном индексе (как в UAP).
    await clan_repo.set_rank(session, actor_id, RANK_MEMBER)
    await clan_repo.set_rank(session, user_id, RANK_OWNER)
    await clan_repo.set_owner(session, actor.clan_id, user_id)
    labels = await clan_repo.member_labels(session, [user_id])
    await clan_repo.log(session, actor.clan_id, f"👑 Клан передан: {labels[user_id][0]}")
    await session.commit()


async def delete(session: AsyncSession, actor_id: int) -> tuple[str, list[int]]:
    """Распустить клан (владелец). → (название, остальные участники — для пушей)."""
    actor = await require_member(session, actor_id, (RANK_OWNER,))
    clan = await clan_repo.get(session, actor.clan_id)
    others = [uid for uid in await clan_repo.member_ids(session, actor.clan_id) if uid != actor_id]
    from bot.services.clan.economy import refund_on_exit

    await refund_on_exit(session, actor.clan_id)  # удаление клана — всем купившим возврат
    await clan_repo.delete_clan(session, actor.clan_id)
    await session.commit()
    return clan.name, others


async def kickable(session: AsyncSession, actor_id: int) -> list[tuple[int, str]]:
    actor = await require_member(session, actor_id, KICK_RANKS)
    members = [m for m in await clan_repo.list_members(session, actor.clan_id) if RANK_LEVEL[m.rank] < RANK_LEVEL[actor.rank]]
    labels = await clan_repo.member_labels(session, [m.user_id for m in members])
    return [(m.user_id, labels[m.user_id][0]) for m in members]


async def kick(session: AsyncSession, actor_id: int, user_id: int) -> str:
    """Кик — только тех, кто ниже рангом (как в UAP). → название клана."""
    actor = await require_member(session, actor_id, KICK_RANKS)
    target = await clan_repo.get_member(session, user_id)
    if target is None or target.clan_id != actor.clan_id:
        raise ClanError("not_member")
    if RANK_LEVEL[target.rank] >= RANK_LEVEL[actor.rank]:
        raise ClanError("higher_rank")
    labels = await clan_repo.member_labels(session, [user_id])
    from bot.services.clan.economy import refund_on_exit

    await refund_on_exit(session, actor.clan_id, user_id)
    await clan_repo.remove_member(session, user_id)
    await clan_repo.log(session, actor.clan_id, f"👢 {labels[user_id][0]} исключён(а)")
    clan = await clan_repo.get(session, actor.clan_id)
    await session.commit()
    return clan.name


async def leave(session: AsyncSession, user_id: int) -> None:
    member = await require_member(session, user_id)
    if member.rank == RANK_OWNER:
        raise ClanError("owner_must_transfer")
    labels = await clan_repo.member_labels(session, [user_id])
    from bot.services.clan.economy import refund_on_exit

    await refund_on_exit(session, member.clan_id, user_id)
    await clan_repo.remove_member(session, user_id)
    await clan_repo.log(session, member.clan_id, f"🚪 {labels[user_id][0]} покинул(а) клан")
    await session.commit()


async def edit(session: AsyncSession, actor_id: int, *, name: str | None = None, description: str | None = None) -> None:
    actor = await require_member(session, actor_id, MANAGER_RANKS)
    try:
        await clan_repo.update_profile(session, actor.clan_id, name=name, description=description)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ClanError("name_taken") from None


async def can_set_image(session: AsyncSession, clan_id: int) -> bool:
    return clan_id in await clan_repo.top_ids(session, CLAN_TOP_IMAGE)


async def set_image(session: AsyncSession, actor_id: int, file_id: str) -> None:
    """Аватарка — только топ-10 кланов (проверка в сервисе, а не только в UI, как в UAP)."""
    actor = await require_member(session, actor_id, MANAGER_RANKS)
    if not await can_set_image(session, actor.clan_id):
        raise ClanError("not_top", CLAN_TOP_IMAGE)
    await clan_repo.update_profile(session, actor.clan_id, image=file_id)
    await session.commit()
