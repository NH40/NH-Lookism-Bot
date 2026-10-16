"""Кланы (репозиторий). Функции записи НЕ коммитят — коммитит сервис (правило 10)."""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.clan import (
    Clan,
    ClanBuilding,
    ClanGarrisonCard,
    ClanGarrisonExtra,
    ClanIncomeShare,
    ClanJoinRequest,
    ClanLog,
    ClanMember,
    ClanWar,
)
from bot.db.models.gang import Gang
from bot.db.models.user import User

_UNSET = object()


# --- клан ---

async def get(session: AsyncSession, clan_id: int, *, for_update: bool = False) -> Clan | None:
    stmt = select(Clan).where(Clan.id == clan_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt.execution_options(populate_existing=True))


async def create(session: AsyncSession, *, name: str, owner_id: int, lands: int) -> Clan | None:
    """Атомарно — None, если имя занято (ON CONFLICT DO NOTHING)."""
    return await session.scalar(
        pg_insert(Clan).values(name=name, owner_id=owner_id, lands=lands).on_conflict_do_nothing(index_elements=[Clan.name]).returning(Clan)
    )


async def update_profile(session: AsyncSession, clan_id: int, *, name: str | None = None, description: str | None = None, image=_UNSET) -> None:
    values: dict = {}
    if name is not None:
        values["name"] = name
    if description is not None:
        values["description"] = description
    if image is not _UNSET:
        values["image_file_id"] = image
    if values:
        await session.execute(update(Clan).where(Clan.id == clan_id).values(**values))


async def set_owner(session: AsyncSession, clan_id: int, owner_id: int) -> None:
    await session.execute(update(Clan).where(Clan.id == clan_id).values(owner_id=owner_id))


async def delete_clan(session: AsyncSession, clan_id: int) -> None:
    await session.execute(delete(Clan).where(Clan.id == clan_id))


async def count_clans(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count(Clan.id))) or 0)


async def top_page(session: AsyncSession, limit: int, offset: int) -> list[tuple[Clan, int]]:
    """Топ кланов: земли, затем число участников, затем старшинство."""
    members = func.count(ClanMember.user_id)
    rows = await session.execute(
        select(Clan, members).outerjoin(ClanMember, ClanMember.clan_id == Clan.id)
        .group_by(Clan.id).order_by(Clan.lands.desc(), members.desc(), Clan.id).limit(limit).offset(offset)
    )
    return [(c, int(n)) for c, n in rows.all()]


async def search_page(session: AsyncSession, query: str, limit: int, offset: int) -> tuple[list[tuple[Clan, int]], int]:
    """Поиск кланов по части названия (без регистра), в том же порядке, что топ. → (страница, всего)."""
    pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    total = int(await session.scalar(select(func.count(Clan.id)).where(Clan.name.ilike(pattern, escape="\\"))) or 0)
    members = func.count(ClanMember.user_id)
    rows = await session.execute(
        select(Clan, members).outerjoin(ClanMember, ClanMember.clan_id == Clan.id).where(Clan.name.ilike(pattern, escape="\\"))
        .group_by(Clan.id).order_by(Clan.lands.desc(), members.desc(), Clan.id).limit(limit).offset(offset)
    )
    return [(c, int(n)) for c, n in rows.all()], total


async def top_ids(session: AsyncSession, limit: int) -> set[int]:
    return {c.id for c, _ in await top_page(session, limit, 0)}


async def change_treasury(session: AsyncSession, clan_id: int, delta: int) -> bool:
    """Казна ± (для минуса — только если хватает, правило 1)."""
    stmt = update(Clan).where(Clan.id == clan_id)
    if delta < 0:
        stmt = stmt.where(Clan.treasury >= -delta)
    result = await session.execute(stmt.values(treasury=Clan.treasury + delta))
    return result.rowcount > 0


# --- участники ---

async def get_member(session: AsyncSession, user_id: int) -> ClanMember | None:
    return await session.scalar(select(ClanMember).where(ClanMember.user_id == user_id).execution_options(populate_existing=True))


async def list_members(session: AsyncSession, clan_id: int) -> Sequence[ClanMember]:
    return (await session.scalars(select(ClanMember).where(ClanMember.clan_id == clan_id).order_by(ClanMember.joined_at))).all()


async def count_members(session: AsyncSession, clan_id: int) -> int:
    return int(await session.scalar(select(func.count()).where(ClanMember.clan_id == clan_id)) or 0)


async def add_member(session: AsyncSession, clan_id: int, user_id: int, rank: str) -> bool:
    result = await session.execute(
        pg_insert(ClanMember).values(clan_id=clan_id, user_id=user_id, rank=rank).on_conflict_do_nothing(index_elements=[ClanMember.user_id])
    )
    return result.rowcount > 0


async def remove_member(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(ClanMember).where(ClanMember.user_id == user_id))


async def set_rank(session: AsyncSession, user_id: int, rank: str) -> None:
    await session.execute(update(ClanMember).where(ClanMember.user_id == user_id).values(rank=rank))


async def member_labels(session: AsyncSession, user_ids: list[int]) -> dict[int, tuple[str, str | None]]:
    """user_id → (название банды или имя, юзернейм) — одним запросом."""
    if not user_ids:
        return {}
    rows = await session.execute(
        select(User.id, Gang.name, User.display_name, User.username).outerjoin(Gang, Gang.user_id == User.id).where(User.id.in_(user_ids))
    )
    return {uid: (gang or display or "—", username) for uid, gang, display, username in rows.all()}


async def officers(session: AsyncSession, clan_id: int) -> dict[str, int]:
    """Ранг → user_id для владельца и заместителя."""
    rows = await session.execute(
        select(ClanMember.rank, ClanMember.user_id).where(ClanMember.clan_id == clan_id, ClanMember.rank.in_(("owner", "deputy")))
    )
    return {r: uid for r, uid in rows.all()}


# --- заявки / приглашения ---

async def create_request(session: AsyncSession, clan_id: int, user_id: int, is_invite: bool) -> bool:
    result = await session.execute(
        pg_insert(ClanJoinRequest).values(clan_id=clan_id, user_id=user_id, is_invite=is_invite)
        .on_conflict_do_nothing(index_elements=[ClanJoinRequest.clan_id, ClanJoinRequest.user_id])
    )
    return result.rowcount > 0


async def get_request(session: AsyncSession, clan_id: int, user_id: int) -> ClanJoinRequest | None:
    return await session.scalar(select(ClanJoinRequest).where(ClanJoinRequest.clan_id == clan_id, ClanJoinRequest.user_id == user_id))


async def list_requests(session: AsyncSession, clan_id: int, is_invite: bool) -> Sequence[ClanJoinRequest]:
    return (await session.scalars(
        select(ClanJoinRequest).where(ClanJoinRequest.clan_id == clan_id, ClanJoinRequest.is_invite.is_(is_invite)).order_by(ClanJoinRequest.created_at)
    )).all()


async def application_of(session: AsyncSession, user_id: int) -> ClanJoinRequest | None:
    return await session.scalar(select(ClanJoinRequest).where(ClanJoinRequest.user_id == user_id, ClanJoinRequest.is_invite.is_(False)))


async def invites_of(session: AsyncSession, user_id: int) -> Sequence[ClanJoinRequest]:
    return (await session.scalars(
        select(ClanJoinRequest).where(ClanJoinRequest.user_id == user_id, ClanJoinRequest.is_invite.is_(True)).order_by(ClanJoinRequest.created_at)
    )).all()


async def delete_request(session: AsyncSession, clan_id: int, user_id: int) -> None:
    await session.execute(delete(ClanJoinRequest).where(ClanJoinRequest.clan_id == clan_id, ClanJoinRequest.user_id == user_id))


async def delete_requests_of(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(ClanJoinRequest).where(ClanJoinRequest.user_id == user_id))


async def names(session: AsyncSession, clan_ids: list[int]) -> dict[int, str]:
    if not clan_ids:
        return {}
    rows = await session.execute(select(Clan.id, Clan.name).where(Clan.id.in_(clan_ids)))
    return {cid: name for cid, name in rows.all()}


# --- здания ---

async def buildings(session: AsyncSession, clan_id: int) -> dict[str, int]:
    rows = await session.execute(select(ClanBuilding.kind, ClanBuilding.count).where(ClanBuilding.clan_id == clan_id, ClanBuilding.count > 0))
    return {k: c for k, c in rows.all()}


async def add_building(session: AsyncSession, clan_id: int, kind: str, delta: int) -> None:
    await session.execute(
        pg_insert(ClanBuilding).values(clan_id=clan_id, kind=kind, count=max(delta, 0))
        .on_conflict_do_update(index_elements=[ClanBuilding.clan_id, ClanBuilding.kind], set_={"count": func.greatest(ClanBuilding.count + delta, 0)})
    )


async def buildings_of_user(session: AsyncSession, user_id: int) -> tuple[int, dict[str, int]] | None:
    """(донат-уровень, здания) клана игрока — для Build одним запросом."""
    rows = (await session.execute(
        select(Clan.donate_level, ClanBuilding.kind, ClanBuilding.count)
        .join(ClanMember, ClanMember.clan_id == Clan.id)
        .outerjoin(ClanBuilding, ClanBuilding.clan_id == Clan.id)
        .where(ClanMember.user_id == user_id)
    )).all()
    if not rows:
        return None
    return rows[0][0], {k: c for _, k, c in rows if k and c}


async def clans_with_building(session: AsyncSession, kind: str) -> list[tuple[int, int]]:
    rows = await session.execute(select(ClanBuilding.clan_id, ClanBuilding.count).where(ClanBuilding.kind == kind, ClanBuilding.count > 0))
    return [(cid, n) for cid, n in rows.all()]


async def member_ids(session: AsyncSession, clan_id: int) -> list[int]:
    return list((await session.scalars(select(ClanMember.user_id).where(ClanMember.clan_id == clan_id))).all())


# --- рота ---

async def garrison_extras(session: AsyncSession, clan_id: int, *, for_update: bool = False) -> Sequence[ClanGarrisonExtra]:
    stmt = select(ClanGarrisonExtra).where(ClanGarrisonExtra.clan_id == clan_id, ClanGarrisonExtra.quantity > 0)
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.scalars(stmt.order_by(ClanGarrisonExtra.rank))).all()


async def garrison_cards(session: AsyncSession, clan_id: int, *, for_update: bool = False) -> Sequence[ClanGarrisonCard]:
    stmt = select(ClanGarrisonCard).where(ClanGarrisonCard.clan_id == clan_id, ClanGarrisonCard.quantity > 0)
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.scalars(stmt.order_by(ClanGarrisonCard.card_code))).all()


async def add_garrison_extra(session: AsyncSession, clan_id: int, key: dict, delta: int) -> None:
    await session.execute(
        pg_insert(ClanGarrisonExtra).values(clan_id=clan_id, quantity=delta, **key)
        .on_conflict_do_update(
            index_elements=[ClanGarrisonExtra.clan_id, ClanGarrisonExtra.rank, ClanGarrisonExtra.stars, ClanGarrisonExtra.training_level,
                            ClanGarrisonExtra.school, ClanGarrisonExtra.school_level],
            set_={"quantity": ClanGarrisonExtra.quantity + delta},
        )
    )


async def take_garrison_extra(session: AsyncSession, clan_id: int, key: dict, amount: int) -> bool:
    """Забрать бойцов роты, если хватает (условный UPDATE, правило 1)."""
    result = await session.execute(
        update(ClanGarrisonExtra)
        .where(ClanGarrisonExtra.clan_id == clan_id, ClanGarrisonExtra.quantity >= amount,
               *(getattr(ClanGarrisonExtra, k) == v for k, v in key.items()))
        .values(quantity=ClanGarrisonExtra.quantity - amount)
    )
    return result.rowcount > 0


async def add_garrison_card(session: AsyncSession, clan_id: int, card_code: str, delta: int) -> None:
    await session.execute(
        pg_insert(ClanGarrisonCard).values(clan_id=clan_id, card_code=card_code, quantity=delta)
        .on_conflict_do_update(index_elements=[ClanGarrisonCard.clan_id, ClanGarrisonCard.card_code], set_={"quantity": ClanGarrisonCard.quantity + delta})
    )


async def take_garrison_card(session: AsyncSession, clan_id: int, card_code: str, amount: int) -> bool:
    result = await session.execute(
        update(ClanGarrisonCard)
        .where(ClanGarrisonCard.clan_id == clan_id, ClanGarrisonCard.card_code == card_code, ClanGarrisonCard.quantity >= amount)
        .values(quantity=ClanGarrisonCard.quantity - amount)
    )
    return result.rowcount > 0


# --- журнал, войны, доля дохода ---

async def log(session: AsyncSession, clan_id: int, line: str) -> None:
    session.add(ClanLog(clan_id=clan_id, text=line[:256]))


async def recent_log(session: AsyncSession, clan_id: int, limit: int) -> Sequence[ClanLog]:
    return (await session.scalars(select(ClanLog).where(ClanLog.clan_id == clan_id).order_by(ClanLog.created_at.desc()).limit(limit))).all()


async def add_war(session: AsyncSession, **values) -> None:
    session.add(ClanWar(**values))


async def recent_wars(session: AsyncSession, clan_id: int, limit: int = 5) -> Sequence[ClanWar]:
    return (await session.scalars(
        select(ClanWar).where((ClanWar.attacker_id == clan_id) | (ClanWar.defender_id == clan_id)).order_by(ClanWar.created_at.desc()).limit(limit)
    )).all()


async def add_share(session: AsyncSession, user_id: int, amount: int) -> None:
    if amount > 0:
        await session.execute(
            pg_insert(ClanIncomeShare).values(user_id=user_id, pending=amount)
            .on_conflict_do_update(index_elements=[ClanIncomeShare.user_id], set_={"pending": ClanIncomeShare.pending + amount})
        )


async def take_share(session: AsyncSession, user_id: int) -> int:
    """Забрать накопленную долю (обнулить) одним запросом."""
    value = await session.scalar(
        text(
            "UPDATE clan_income_shares s SET pending = 0 FROM (SELECT pending FROM clan_income_shares WHERE user_id = :u FOR UPDATE) old "
            "WHERE s.user_id = :u RETURNING old.pending"
        ),
        {"u": user_id},
    )
    return int(value or 0)


async def pending_share(session: AsyncSession, user_id: int) -> int:
    return int(await session.scalar(select(ClanIncomeShare.pending).where(ClanIncomeShare.user_id == user_id)) or 0)


async def settle_income_share(session: AsyncSession, user_id: int, amount: int, owner_share: float, deputy_share: float) -> int:
    """Шаг зачисления дохода игрока (НЕ коммитит): владельцу и заму его клана — доля `amount`
    сверху, а самому игроку — его накопленная доля (если он владелец/зам). Строки долей
    берутся строго по возрастанию user_id: владелец и зам начисляют друг другу, и встречные
    зачисления без общего порядка заблокировали бы друг друга. → сколько забрал сам игрок."""
    member = await session.scalar(select(ClanMember.clan_id).where(ClanMember.user_id == user_id))
    adds: dict[int, int] = {}
    if member is not None and amount > 0:
        for rank, uid in (await officers(session, member)).items():
            if uid != user_id:
                share = int(amount * (owner_share if rank == "owner" else deputy_share))
                if share:
                    adds[uid] = adds.get(uid, 0) + share
    taken = 0
    for uid in sorted({user_id, *adds}):
        if uid == user_id:
            taken = await take_share(session, user_id)
        else:
            await add_share(session, uid, adds[uid])
    return taken


async def request_garrison_access(session: AsyncSession, user_id: int) -> bool:
    """Поставить запрос доступа к роте (если его ещё нет и доступ не дан)."""
    result = await session.execute(
        update(ClanMember)
        .where(ClanMember.user_id == user_id, ClanMember.garrison_approved.is_(False), ClanMember.garrison_request_at.is_(None))
        .values(garrison_request_at=func.now())
    )
    return result.rowcount > 0


async def set_garrison_access(session: AsyncSession, clan_id: int, user_id: int, allowed: bool) -> bool:
    """Выдать или отнять право забирать из роты (владелец, 2026-10-12). Снимает ждущий запрос."""
    result = await session.execute(
        update(ClanMember)
        .where(ClanMember.user_id == user_id, ClanMember.clan_id == clan_id)
        .values(garrison_approved=allowed, garrison_request_at=None)
    )
    return result.rowcount > 0


async def resolve_garrison_access(session: AsyncSession, clan_id: int, user_id: int, approved: bool) -> bool:
    """Одобрить или отклонить ждущий запрос (условный UPDATE: двойной клик не сработает дважды)."""
    values = {"garrison_request_at": None}
    if approved:
        values["garrison_approved"] = True
    result = await session.execute(
        update(ClanMember)
        .where(ClanMember.user_id == user_id, ClanMember.clan_id == clan_id, ClanMember.garrison_request_at.is_not(None))
        .values(**values)
    )
    return result.rowcount > 0


async def garrison_requests(session: AsyncSession, clan_id: int) -> Sequence[ClanMember]:
    return (await session.scalars(
        select(ClanMember).where(ClanMember.clan_id == clan_id, ClanMember.garrison_request_at.is_not(None)).order_by(ClanMember.garrison_request_at)
    )).all()


# --- донат-уровни ---


async def lock_clan(session: AsyncSession, clan_id: int) -> Clan | None:
    return await session.scalar(select(Clan).where(Clan.id == clan_id).with_for_update().execution_options(populate_existing=True))


async def add_donate_purchase(session: AsyncSession, clan_id: int, user_id: int, price: int) -> None:
    await session.execute(
        text(
            "WITH ins AS (INSERT INTO clan_donate_purchases (clan_id, user_id, price) VALUES (:c, :u, :p) RETURNING clan_id) "
            "UPDATE clans SET donate_level = donate_level + 1 WHERE id IN (SELECT clan_id FROM ins)"
        ),
        {"c": clan_id, "u": user_id, "p": price},
    )


async def refund_donate(session: AsyncSession, clan_id: int, user_id: int | None = None) -> list[tuple[int, int]]:
    """Снять покупки (одного игрока или все) и вернуть уплаченное донат-коинами; уровень клана
    пересчитывается по оставшимся покупкам. → [(игрок, возвращено)]."""
    rows = (
        await session.execute(
            text(
                "DELETE FROM clan_donate_purchases WHERE clan_id = :c AND (CAST(:u AS bigint) IS NULL OR user_id = CAST(:u AS bigint)) "
                "RETURNING user_id, price"
            ),
            {"c": clan_id, "u": user_id},
        )
    ).all()
    refunds: dict[int, int] = {}
    for uid, price in rows:
        refunds[uid] = refunds.get(uid, 0) + price
    for uid, amount in refunds.items():
        await session.execute(text("UPDATE users SET donate_coins = donate_coins + :a WHERE id = :u"), {"u": uid, "a": amount})
    if rows:
        await session.execute(
            text("UPDATE clans SET donate_level = (SELECT count(*) FROM clan_donate_purchases WHERE clan_id = :c) WHERE id = :c"),
            {"c": clan_id},
        )
    return list(refunds.items())


async def donate_buyers(session: AsyncSession, clan_id: int) -> list[tuple[int, int]]:
    """[(игрок, уплачено)] в порядке покупки."""
    rows = await session.execute(
        text("SELECT user_id, price FROM clan_donate_purchases WHERE clan_id = :c ORDER BY id"), {"c": clan_id}
    )
    return [(u, p) for u, p in rows.all()]
