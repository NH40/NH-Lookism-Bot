"""API-роутер Mini App для домена clan — полное управление кланом.

Только сервисы бота (`bot.services.clan`: clan / economy / garrison / war): роутер проверяет
ввод, зовёт сервис, ловит `ClanError` и отдаёт текст из `bot.texts.clan.ERRORS` (тот же маппинг,
что `bot.handlers.clan.error_text`). Права проверяют сами сервисы; `can` в ответе нужен лишь
чтобы UI показывал игроку только допустимые действия. Пуши второй стороне шлёт `api.push` теми же текстами/категориями, что хендлеры бота."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.push import push, push_many
from api.routers._common import bad, clean_label, require_user
from bot.config.card import CARD_BY_CODE
from bot.config.clan import (
    CLAN_BUILDINGS,
    CLAN_CREATE_COST,
    CLAN_DEMOLISH_REFUND,
    CLAN_DONATE_LEVELS,
    CLAN_MAX_MEMBERS,
    CLAN_NAME_MAX,
    CLAN_NAME_MIN,
    CLAN_PAGE,
    CLAN_TOP_IMAGE,
    building_price,
    clan_donate_price,
)
from bot.constant.clan import BUILDINGS, KICK_RANKS, MANAGER_RANKS, RANK_CAPTAIN, RANK_DEPUTY, RANK_LEVEL, RANK_MEMBER, RANK_OWNER
from bot.db.repositories import card as card_repo
from bot.db.repositories import clan as clan_repo
from bot.services import clan as clan_service
from bot.services.clan import ClanError
from bot.services.extra import list_squads
from bot.constant.resource import RES_COINS, RES_DONATE
from bot.constant.settings import NOTIFY_CLAN, NOTIFY_CLAN_WAR
from bot.handlers.clan.garrison import war_result_text
from bot.services.resource import StatistKey, balance, balances
from bot.constant.resource import RESOURCES
from bot.texts.resource import amount_label, resource_label
from bot.texts.clan import (
    BUILDING_ABOUT,
    BUILDING_NAMES,
    ERRORS,
    PUSH_ACCEPTED,
    PUSH_APPLICATION,
    PUSH_GAR_APPROVED,
    PUSH_GAR_DENIED,
    PUSH_GAR_REQUEST,
    PUSH_GAR_REVOKED,
    PUSH_INVITE,
    PUSH_DELETED,
    PUSH_EXCHANGE,
    PUSH_KICKED,
    RANK_NAME,
)
from bot.texts.gang import squad_title
from bot.utils.formatting import esc, format_number

router = APIRouter(prefix="/api/clan", tags=["clan"])

_SET_RANKS = (RANK_DEPUTY, RANK_CAPTAIN, RANK_MEMBER)


def _err(exc: ClanError) -> Exception:
    value = format_number(exc.value) if isinstance(exc.value, int) else exc.value
    return bad(ERRORS.get(exc.code, exc.code).format(value=value))


async def _me(session: AsyncSession, user_id: int):
    await require_user(session, user_id)
    member = await clan_service.member_of(session, user_id)
    if member is None:
        raise bad(ERRORS["not_in_clan"])
    return member


def _ok(message: str, **extra) -> dict:
    return {"message": message, **extra}


def _label(labels: dict, uid: int) -> tuple[str, str | None]:
    return labels.get(uid, ("—", None))


# --- модели ответов ---

class ClanCardOut(BaseModel):
    clan_id: int
    name: str
    members: int
    max_members: int
    lands: int
    donate_level: int
    top10: bool
    applied: bool


class BrowseOut(BaseModel):
    items: list[ClanCardOut]
    page: int
    pages: int
    total: int


class InviteOut(BaseModel):
    clan_id: int
    name: str


class NoClanOut(BaseModel):
    coins: int
    create_cost: int
    name_min: int
    name_max: int
    application: InviteOut | None
    invites: list[InviteOut]
    browse: BrowseOut


class MemberOut(BaseModel):
    user_id: int
    name: str
    username: str | None
    rank: str
    rank_label: str
    is_me: bool
    can_kick: bool
    can_rank: bool
    garrison_access: bool = False  # может забирать из роты (владелец — всегда)
    can_access: bool = False  # смотрящий (владелец) может выдать/отнять право


class PersonOut(BaseModel):
    user_id: int
    name: str
    username: str | None


class CanOut(BaseModel):
    manage: bool
    kick: bool
    set_rank: bool
    transfer: bool
    leave: bool


class ClanOut(BaseModel):
    clan_id: int
    name: str
    description: str | None
    members: list[MemberOut]
    max_members: int
    lands: int
    max_lands: int
    treasury: int
    donate_level: int
    max_donate_level: int
    next_donate_price: int | None
    donate_buyers: list[str]
    power: int
    requests: list[PersonOut]
    access_requests: list[PersonOut]
    set_ranks: list[dict]


class ClanResponse(BaseModel):
    clan: ClanOut | None
    my_rank: str | None = None
    my_rank_label: str | None = None
    can: CanOut | None = None
    coins: int = 0
    donate_coins: int = 0
    no_clan: NoClanOut | None = None


async def _cards(session: AsyncSession, rows, applied_id: int | None, top: set[int]) -> list[ClanCardOut]:
    return [
        ClanCardOut(
            clan_id=c.id, name=c.name, members=n, max_members=CLAN_MAX_MEMBERS, lands=c.lands,
            donate_level=c.donate_level, top10=c.id in top, applied=c.id == applied_id,
        )
        for c, n in rows
    ]


async def _browse(session: AsyncSession, page: int, query: str, applied_id: int | None) -> BrowseOut:
    top = await clan_repo.top_ids(session, CLAN_TOP_IMAGE)
    if query:
        total = (await clan_repo.search_page(session, query, 1, 0))[1]
        pages = max(1, -(-total // CLAN_PAGE))
        page = max(0, min(page, pages - 1))
        rows, _ = await clan_repo.search_page(session, query, CLAN_PAGE, page * CLAN_PAGE)
    else:
        rows, page, pages = await clan_service.browse(session, page, CLAN_PAGE)
        total = await clan_repo.count_clans(session)
    return BrowseOut(items=await _cards(session, rows, applied_id, top), page=page, pages=pages, total=total)


# --- обзор ---

@router.get("", response_model=ClanResponse)
async def get_my_clan(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> ClanResponse:
    await require_user(session, user_id)
    coins = await balance(session, user_id, RES_COINS)
    me = await clan_service.member_of(session, user_id)
    if me is None:
        app = await clan_repo.application_of(session, user_id)
        invites = await clan_repo.invites_of(session, user_id)
        names = await clan_repo.names(session, [r.clan_id for r in invites] + ([app.clan_id] if app else []))
        return ClanResponse(
            clan=None, coins=coins,
            no_clan=NoClanOut(
                coins=coins, create_cost=CLAN_CREATE_COST, name_min=CLAN_NAME_MIN, name_max=CLAN_NAME_MAX,
                application=InviteOut(clan_id=app.clan_id, name=names.get(app.clan_id, "—")) if app else None,
                invites=[InviteOut(clan_id=r.clan_id, name=names.get(r.clan_id, "—")) for r in invites],
                browse=await _browse(session, 0, "", app.clan_id if app else None),
            ),
        )

    clan = await clan_repo.get(session, me.clan_id)
    members = await clan_repo.list_members(session, clan.id)
    buyers = await clan_repo.donate_buyers(session, clan.id)
    manage = me.rank in MANAGER_RANKS
    requests = list(await clan_repo.list_requests(session, clan.id, False)) if manage else []
    access = await clan_service.access_requests(session, user_id) if me.rank == RANK_OWNER else []
    ids = list({m.user_id for m in members} | {u for u, _ in buyers} | {r.user_id for r in requests})
    labels = await clan_repo.member_labels(session, ids)
    members = sorted(members, key=lambda m: (-RANK_LEVEL[m.rank], m.joined_at))
    can_kick_any = me.rank in KICK_RANKS
    return ClanResponse(
        clan=ClanOut(
            clan_id=clan.id, name=clan.name, description=clan.description,
            members=[
                MemberOut(
                    user_id=m.user_id, name=_label(labels, m.user_id)[0], username=_label(labels, m.user_id)[1],
                    rank=m.rank, rank_label=RANK_NAME.get(m.rank, m.rank), is_me=m.user_id == user_id,
                    can_kick=can_kick_any and RANK_LEVEL[m.rank] < RANK_LEVEL[me.rank],
                    can_rank=me.rank == RANK_OWNER and m.rank != RANK_OWNER,
                    garrison_access=m.rank == RANK_OWNER or m.garrison_approved,
                    can_access=me.rank == RANK_OWNER and m.rank != RANK_OWNER,
                )
                for m in members
            ],
            max_members=CLAN_MAX_MEMBERS, lands=clan.lands, max_lands=clan_service.max_lands(clan),
            treasury=clan.treasury, donate_level=clan.donate_level, max_donate_level=len(CLAN_DONATE_LEVELS),
            next_donate_price=clan_donate_price(clan.donate_level + 1) if clan.donate_level < len(CLAN_DONATE_LEVELS) else None,
            donate_buyers=[_label(labels, u)[0] for u, _ in buyers],
            power=await clan_service.clan_power(session, clan.id),
            requests=[PersonOut(user_id=r.user_id, name=_label(labels, r.user_id)[0], username=_label(labels, r.user_id)[1]) for r in requests],
            access_requests=[PersonOut(user_id=u, name=n, username=None) for u, n in access],
            set_ranks=[{"rank": r, "label": RANK_NAME[r]} for r in _SET_RANKS],
        ),
        my_rank=me.rank, my_rank_label=RANK_NAME.get(me.rank, me.rank),
        can=CanOut(
            manage=manage, kick=can_kick_any, set_rank=me.rank == RANK_OWNER, transfer=me.rank == RANK_OWNER,
            leave=me.rank != RANK_OWNER,
        ),
        coins=coins, donate_coins=await balance(session, user_id, RES_DONATE),
    )


@router.get("/browse", response_model=BrowseOut)
async def browse_clans(
    page: int = 0, q: str = "", user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> BrowseOut:
    await require_user(session, user_id)
    app = await clan_repo.application_of(session, user_id)
    return await _browse(session, max(0, page), q.strip()[:CLAN_NAME_MAX], app.clan_id if app else None)


# --- без клана ---

class ClanIdIn(BaseModel):
    clan_id: int


class CreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


@router.post("/apply")
async def apply(body: ClanIdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    try:
        await clan_service.apply(session, user_id, body.clan_id)
    except ClanError as exc:
        raise _err(exc) from None
    clan = await clan_repo.get(session, body.clan_id)
    name = (await clan_repo.member_labels(session, [user_id]))[user_id][0]
    for officer in (await clan_repo.officers(session, body.clan_id)).values():
        await push(officer, NOTIFY_CLAN, PUSH_APPLICATION.format(name=esc(name), clan=esc(clan.name)))
    return _ok("Заявка отправлена.")


@router.post("/cancel-application")
async def cancel_application(body: ClanIdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    await clan_service.cancel_application(session, user_id, body.clan_id)
    return _ok("Заявка отменена.")


@router.post("/invite/accept")
async def accept_invite(body: ClanIdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    try:
        await clan_service.accept_invite(session, user_id, body.clan_id)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok("Ты в клане.")


@router.post("/invite/decline")
async def decline_invite(body: ClanIdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    await clan_service.decline_invite(session, user_id, body.clan_id)
    return _ok("Приглашение отклонено.")


@router.post("/create")
async def create_clan(body: CreateIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    name = body.name.strip()
    if not (CLAN_NAME_MIN <= len(name) <= CLAN_NAME_MAX) or "\n" in name:
        raise bad(f"Название: от {CLAN_NAME_MIN} до {CLAN_NAME_MAX} символов, в одну строку.")
    try:
        clan = await clan_service.create(session, user_id, name)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"Клан «{clan.name}» основан.")


# --- состав ---

class UserIdIn(BaseModel):
    user_id: int


class UsernameIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class RankIn(BaseModel):
    user_id: int
    rank: str


class ResolveIn(BaseModel):
    user_id: int
    approved: bool


@router.post("/requests/accept")
async def accept_request(body: UserIdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    try:
        clan_id = await clan_service.accept(session, user_id, body.user_id)
    except ClanError as exc:
        raise _err(exc) from None
    clan = await clan_repo.get(session, clan_id)
    await push(body.user_id, NOTIFY_CLAN, PUSH_ACCEPTED.format(clan=esc(clan.name)))
    return _ok("Игрок принят в клан.")


@router.post("/requests/reject")
async def reject_request(body: UserIdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    try:
        await clan_service.reject(session, user_id, body.user_id)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok("Заявка отклонена.")


@router.post("/invite")
async def invite(body: UsernameIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    try:
        target_id, clan_id = await clan_service.invite(session, user_id, body.username)
    except ClanError as exc:
        raise _err(exc) from None
    clan = await clan_repo.get(session, clan_id)
    await push(target_id, NOTIFY_CLAN, PUSH_INVITE.format(clan=esc(clan.name)))
    return _ok("Приглашение отправлено.")


@router.post("/kick")
async def kick(body: UserIdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    try:
        clan_name = await clan_service.kick(session, user_id, body.user_id)
    except ClanError as exc:
        raise _err(exc) from None
    await push(body.user_id, NOTIFY_CLAN, PUSH_KICKED.format(clan=esc(clan_name)))
    return _ok("Игрок исключён.")


@router.post("/rank")
async def set_rank(body: RankIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    try:
        await clan_service.set_rank(session, user_id, body.user_id, body.rank)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"Ранг: {RANK_NAME.get(body.rank, body.rank)}.")


@router.post("/transfer")
async def transfer(body: UserIdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    try:
        await clan_service.transfer(session, user_id, body.user_id)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok("Клан передан.")


@router.post("/leave")
async def leave(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    try:
        await clan_service.leave(session, user_id)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok("Ты покинул(а) клан.")


class DeleteIn(BaseModel):
    confirm_name: str  # защита от случайного нажатия: название клана целиком


@router.post("/delete")
async def delete_clan(body: DeleteIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    """Распустить клан (владелец). Как в боте: всем купившим клановый донат — возврат."""
    member = await _me(session, user_id)
    clan = await clan_repo.get(session, member.clan_id)
    if clan is None or body.confirm_name.strip().lower() != clan.name.lower():
        raise bad("Для подтверждения впиши название клана точно.")
    try:
        name, others = await clan_service.delete(session, user_id)
    except ClanError as exc:
        raise _err(exc) from None
    await push_many(others, NOTIFY_CLAN, PUSH_DELETED.format(clan=esc(name)))
    return _ok(f"Клан «{name}» распущен.")


class ExchangeResourceOut(BaseModel):
    code: str
    name: str
    balance: int


@router.get("/exchange", response_model=list[ExchangeResourceOut])
async def exchange_options(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> list[ExchangeResourceOut]:
    """Ресурсы обменника клана с балансом игрока (тот же список, что в боте)."""
    await _me(session, user_id)
    have = await balances(session, user_id)
    return [ExchangeResourceOut(code=c, name=clean_label(resource_label(c)), balance=have[c]) for c in RESOURCES]


class ExchangeIn(BaseModel):
    user_id: int
    resource: str
    amount: int


@router.post("/exchange")
async def exchange(
    body: ExchangeIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await require_user(session, user_id)
    try:
        await clan_service.exchange(session, redis, user_id, body.user_id, body.resource, body.amount)
    except ClanError as exc:
        raise _err(exc) from None
    labels = await clan_repo.member_labels(session, [user_id, body.user_id])
    amount = amount_label(body.resource, body.amount)
    await push(body.user_id, NOTIFY_CLAN, PUSH_EXCHANGE.format(name=esc(labels[user_id][0]), amount=amount))
    return _ok(f"Передано {clean_label(amount)}: {clean_label(labels[body.user_id][0])}.")


# --- земли ---

class BuildingOut(BaseModel):
    kind: str
    name: str
    about: str
    count: int
    max: int
    next_price: int | None
    refund: int


class LandsOut(BaseModel):
    lands: int
    max_lands: int
    used: int
    free: int
    treasury: int
    next_land_price: int | None
    buildings: list[BuildingOut]
    coins: int
    donate_level: int
    max_donate_level: int
    next_donate_price: int | None
    donate_coins: int
    donate_buyers: list[str]


@router.get("/lands", response_model=LandsOut)
async def get_lands(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> LandsOut:
    await _me(session, user_id)
    lv = await clan_service.lands_view(session, user_id)
    buyers = await clan_repo.donate_buyers(session, lv.clan.id)
    labels = await clan_repo.member_labels(session, [u for u, _ in buyers])
    out = []
    for kind in BUILDINGS:
        have = lv.buildings.get(kind, 0)
        cap = CLAN_BUILDINGS[kind][0]
        out.append(BuildingOut(
            kind=kind, name=clean_label(BUILDING_NAMES[kind]), about=BUILDING_ABOUT.get(kind, ""), count=have, max=cap,
            next_price=building_price(kind, have) if have < cap else None,
            refund=int(building_price(kind, have - 1) * CLAN_DEMOLISH_REFUND) if have else 0,
        ))
    level = lv.clan.donate_level
    return LandsOut(
        lands=lv.clan.lands, max_lands=lv.max_lands, used=lv.used, free=max(0, lv.clan.lands - lv.used),
        treasury=lv.clan.treasury, next_land_price=lv.next_land_price, buildings=out,
        coins=await balance(session, user_id, RES_COINS), donate_level=level, max_donate_level=len(CLAN_DONATE_LEVELS),
        next_donate_price=clan_donate_price(level + 1) if level < len(CLAN_DONATE_LEVELS) else None,
        donate_coins=await balance(session, user_id, RES_DONATE), donate_buyers=[_label(labels, u)[0] for u, _ in buyers],
    )


class AmountIn(BaseModel):
    amount: int = Field(ge=1, le=10**12)


class KindIn(BaseModel):
    kind: str


@router.post("/donate")
async def donate_treasury(
    body: AmountIn, user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    await require_user(session, user_id)
    try:
        treasury = await clan_service.donate(session, redis, user_id, body.amount)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"В казну внесено {format_number(body.amount)} NHCoin.", treasury=treasury)


@router.post("/buy-land")
async def buy_land(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    await require_user(session, user_id)
    try:
        lands = await clan_service.buy_land(session, redis, user_id)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"Земля освоена, всего {lands}.", lands=lands)


@router.post("/build")
async def build(
    body: KindIn, user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    await require_user(session, user_id)
    try:
        count = await clan_service.build(session, redis, user_id, body.kind)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"{clean_label(BUILDING_NAMES[body.kind])} построено, теперь {count}.", count=count)


@router.post("/demolish")
async def demolish(
    body: KindIn, user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    await require_user(session, user_id)
    try:
        refund = await clan_service.demolish(session, redis, user_id, body.kind)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"Снесено, в казну вернулось {format_number(refund)} NHCoin.", refund=refund)


@router.post("/buy-donate-level")
async def buy_donate_level(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    await require_user(session, user_id)
    try:
        level = await clan_service.buy_donate_level(session, redis, user_id)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"Уровень клана: {level}.", level=level)


# --- рота ---

class StatistOut(BaseModel):
    key: str
    title: str
    quantity: int
    power: int


class CardOut(BaseModel):
    code: str
    name: str
    quantity: int
    power: int
    image: str | None


class GarrisonContractOut(BaseModel):
    rank: str
    quantity: int
    power: int
    left_seconds: int


class GarrisonOut(BaseModel):
    power: int
    statists: list[StatistOut]
    cards: list[CardOut]
    can_take: bool
    take_in_seconds: int
    needs_approval: bool
    pending: bool
    my_statists: list[StatistOut]
    my_cards: list[CardOut]
    contracts: list[GarrisonContractOut] = []


def _title(key: StatistKey) -> str:
    return clean_label(squad_title(key.rank, key.stars, key.training_level, key.school, key.school_level))


@router.get("/garrison", response_model=GarrisonOut)
async def get_garrison(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> GarrisonOut:
    await _me(session, user_id)
    gv = await clan_service.garrison_view(session, user_id)
    squads = [sq for sq in await list_squads(session, user_id) if sq.attack + sq.defense > 0]
    totals: dict[str, int] = {}
    for s in await card_repo.list_stacks(session, user_id):
        totals[s.card_code] = totals.get(s.card_code, 0) + s.quantity

    def card(code: str, qty: int) -> CardOut:
        c = CARD_BY_CODE.get(code)
        return CardOut(code=code, name=c.name if c else code, quantity=qty, power=c.power if c else 0, image=c.image if c else None)

    return GarrisonOut(
        power=gv.power,
        statists=[StatistOut(key=k.encode(), title=_title(k), quantity=q, power=round(p)) for k, q, p in gv.statists],
        cards=[card(code, q).model_copy(update={"power": p}) for code, q, p in gv.cards],
        can_take=gv.can_take, take_in_seconds=gv.take_in_seconds, needs_approval=gv.needs_approval, pending=gv.pending,
        my_statists=[
            StatistOut(
                key=(k := StatistKey(sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level)).encode(),
                title=_title(k), quantity=sq.attack + sq.defense, power=round(sq.unit_power),
            )
            for sq in squads
        ],
        my_cards=[card(code, q) for code, q in sorted(totals.items()) if q > 0 and code in CARD_BY_CODE],
        contracts=[GarrisonContractOut(rank=r, quantity=q, power=round(p), left_seconds=left) for r, q, p, left in gv.contracts],
    )


class StatistIn(BaseModel):
    key: str
    amount: int = Field(ge=1, le=10**9)


class CardIn(BaseModel):
    code: str
    amount: int = Field(ge=1, le=10**9)


def _key(raw: str) -> StatistKey:
    try:
        return StatistKey.decode(raw)
    except ValueError:
        raise bad(ERRORS["bad_item"]) from None


@router.post("/garrison/put-statists")
async def put_statists(
    body: StatistIn, user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    await _me(session, user_id)
    try:
        await clan_service.put_statists(session, redis, user_id, _key(body.key), body.amount)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"Внесено в роту: {body.amount}.")


@router.post("/garrison/put-cards")
async def put_cards(
    body: CardIn, user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    await _me(session, user_id)
    try:
        await clan_service.put_cards(session, redis, user_id, body.code, body.amount)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"Уники внесены в роту: {body.amount}.")


@router.post("/garrison/take-statists")
async def take_statists(
    body: StatistIn, user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    await _me(session, user_id)
    try:
        await clan_service.take_statists_from(session, redis, user_id, _key(body.key), body.amount)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"Забрано из роты: {body.amount}.")


@router.post("/garrison/take-cards")
async def take_cards(
    body: CardIn, user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    await _me(session, user_id)
    try:
        await clan_service.take_cards_from(session, redis, user_id, body.code, body.amount)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"Уники забраны из роты: {body.amount}.")


@router.post("/garrison/request-access")
async def request_access(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await _me(session, user_id)
    try:
        clan_id = await clan_service.request_access(session, user_id)
    except ClanError as exc:
        raise _err(exc) from None
    name = (await clan_repo.member_labels(session, [user_id]))[user_id][0]
    for officer in (await clan_repo.officers(session, clan_id)).values():
        await push(officer, NOTIFY_CLAN, PUSH_GAR_REQUEST.format(name=esc(name)))
    return _ok("Запрос отправлен владельцу клана.")


@router.post("/garrison/resolve-access")
async def resolve_access(body: ResolveIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await _me(session, user_id)
    try:
        if body.approved:
            await clan_service.set_access(session, user_id, body.user_id, True)
        else:
            await clan_service.resolve_access(session, user_id, body.user_id, False)
    except ClanError as exc:
        raise _err(exc) from None
    await push(body.user_id, NOTIFY_CLAN, PUSH_GAR_APPROVED if body.approved else PUSH_GAR_DENIED)
    return _ok("Доступ выдан." if body.approved else "Доступ отклонён.")


class AccessIn(BaseModel):
    user_id: int
    allowed: bool


@router.post("/garrison/access")
async def set_access(body: AccessIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    """Владелец выдаёт или отнимает у участника право забирать из роты."""
    await _me(session, user_id)
    try:
        await clan_service.set_access(session, user_id, body.user_id, body.allowed)
    except ClanError as exc:
        raise _err(exc) from None
    await push(body.user_id, NOTIFY_CLAN, PUSH_GAR_APPROVED if body.allowed else PUSH_GAR_REVOKED)
    return _ok("Доступ к роте выдан." if body.allowed else "Доступ к роте отнят.")


# --- война ---

class TargetOut(BaseModel):
    clan_id: int
    name: str
    lands: int
    members: int
    shielded: bool


class WarRowOut(BaseModel):
    attacker: str
    defender: str
    won_by_me: bool
    i_attacked: bool
    lands_taken: int
    treasury_taken: int
    created_at: str


class WarOut(BaseModel):
    targets: list[TargetOut]
    page: int
    pages: int
    cooldown_seconds: int
    shield_seconds: int
    power: int
    can_attack: bool
    history: list[WarRowOut]


@router.get("/war", response_model=WarOut)
async def get_war(
    page: int = 0, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> WarOut:
    me = await _me(session, user_id)
    targets, page, pages = await clan_service.targets(session, user_id, max(0, page))
    clan = await clan_service.my_clan(session, user_id)
    wars = await clan_service.history(session, clan.id)
    return WarOut(
        targets=[TargetOut(clan_id=t.clan_id, name=t.name, lands=t.lands, members=t.members, shielded=t.shielded) for t in targets],
        page=page, pages=pages,
        cooldown_seconds=clan_service.cooldown_left(clan), shield_seconds=clan_service.shield_left(clan),
        power=await clan_service.clan_power(session, clan.id), can_attack=me.rank in MANAGER_RANKS,
        history=[
            WarRowOut(
                attacker=w.attacker_name, defender=w.defender_name, i_attacked=w.attacker_id == clan.id,
                won_by_me=w.attacker_won == (w.attacker_id == clan.id), lands_taken=w.lands_taken,
                treasury_taken=w.treasury_taken, created_at=w.created_at.isoformat(),
            )
            for w in wars
        ],
    )


@router.post("/war/attack")
async def war_attack(
    body: ClanIdIn, user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    await _me(session, user_id)
    try:
        r = await clan_service.attack(session, redis, user_id, body.clan_id)
    except ClanError as exc:
        raise _err(exc) from None
    await push_many({*r.attacker_members, *r.defender_members} - {user_id}, NOTIFY_CLAN_WAR, war_result_text(r))
    message = (
        f"Победа над «{r.defender_name}»: земель +{r.lands_gained}, казна +{format_number(r.treasury_taken)}."
        if r.attacker_won else f"Поражение от «{r.defender_name}»."
    )
    return _ok(
        message, won=r.attacker_won, rounds=r.rounds, attacker_power=r.attacker_power, defender_power=r.defender_power,
        attacker_dead=r.attacker_dead, defender_dead=r.defender_dead, lands_taken=r.lands_taken,
        lands_gained=r.lands_gained, treasury_taken=r.treasury_taken, defender_name=r.defender_name,
    )


# ---------------------------------------------------------------- магазин клана (2026-10-20)
# Тот же магазин, что в боте (`handlers/clan/economy`): тикеты и зелья каждому участнику, контрактники
# в роту на сутки — из казны, покупают владелец и зам (права проверяет сервис).

class ShopTicketsIn(BaseModel):
    tickets: int


class ShopPotionIn(BaseModel):
    kind: str
    tier: int


class ShopContractsIn(BaseModel):
    rank: str
    quantity: int = Field(gt=0)


@router.get("/shop")
async def get_shop(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    from bot.config.clan import CLAN_CONTRACT_HOURS, CLAN_SHOP_POTION_TIERS, CLAN_SHOP_TICKET_PRICE, CLAN_SHOP_TICKETS_MAX
    from bot.constant.potion import POTION_WEALTH, POTIONS
    from bot.services.contract import terms as contract_terms
    from bot.texts.potion import POTION_NAMES

    await require_user(session, user_id)
    member = await clan_service.member_of(session, user_id)
    if member is None:
        raise bad("Ты не в клане.")
    clan = await clan_repo.get(session, member.clan_id)
    members = await clan_repo.count_members(session, clan.id)
    t = await contract_terms(session, user_id)
    return {
        "treasury": clan.treasury, "members": members, "can_buy": member.rank in MANAGER_RANKS,
        "tickets": [{"tickets": n, "price": clan_service.tickets_price(n, members)} for n in (1, 5, 10)],
        "ticket_price": CLAN_SHOP_TICKET_PRICE, "tickets_max": CLAN_SHOP_TICKETS_MAX,
        "potions": [
            {"kind": k, "name": clean_label(POTION_NAMES[k]),
             "tiers": [{"tier": tier, "price": clan_service.potion_price(tier, members)} for tier in CLAN_SHOP_POTION_TIERS]}
            for k in POTIONS if k != POTION_WEALTH
        ],
        "contracts": {
            "hours": CLAN_CONTRACT_HOURS, "ceiling": t.ceiling,
            "ranks": [{"rank": r, "price": clan_service.contract_unit_price(r)} for r in t.ranks[:12]],
        },
    }


@router.post("/shop/tickets")
async def post_shop_tickets(
    body: ShopTicketsIn, user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    await require_user(session, user_id)
    try:
        price, members = await clan_service.shop_tickets(session, redis, user_id, body.tickets)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"Всем {members} участникам по {body.tickets} тикет. — из казны {format_number(price)} NHCoin.")


@router.post("/shop/potion")
async def post_shop_potion(
    body: ShopPotionIn, user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    await require_user(session, user_id)
    try:
        price, members = await clan_service.shop_potion(session, redis, user_id, body.kind, body.tier)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"Зелье выпили все {members} участников — из казны {format_number(price)} NHCoin.")


@router.post("/shop/contracts")
async def post_shop_contracts(
    body: ShopContractsIn, user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis),
) -> dict:
    from bot.config.clan import CLAN_CONTRACT_HOURS
    from bot.services.contract import terms as contract_terms

    await require_user(session, user_id)
    t = await contract_terms(session, user_id)
    try:
        price = await clan_service.shop_contracts(session, redis, user_id, body.rank, body.quantity, t.ceiling)
    except ClanError as exc:
        raise _err(exc) from None
    return _ok(f"Контракт: {format_number(body.quantity)} × {body.rank} в роту на {CLAN_CONTRACT_HOURS} ч — из казны {format_number(price)} NHCoin.")



@router.get("/stats")
async def get_stats(sort: str = "treasury", user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    """Вклад участников клана (2026-10-21) — те же счётчики, что экран «📊 Вклад» в боте."""
    await require_user(session, user_id)
    try:
        rows = await clan_service.member_stats(session, user_id, sort)
    except ClanError as exc:
        raise _err(exc) from None
    return {"sort": sort, "rows": [
        {"user_id": r["user_id"], "name": r["name"], "rank": r["rank"], "is_me": r["user_id"] == user_id,
         "joined_at": r["joined_at"].isoformat() if r["joined_at"] else None,
         "last_active": r["last_active_at"].isoformat() if r["last_active_at"] else None,
         **{k: int(r[k]) for k in ("treasury", "garrison_units", "garrison_power", "garrison_taken", "shop_spent",
                                   "build_spent", "wars", "wars_won", "lands_won", "exchanges")}}
        for r in rows
    ]}
