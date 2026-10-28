"""API-роутер Mini App для домена profile.

Бизнес-логика — ТОЛЬКО через `bot.services.profile` (тот же сервис, что вызывает и
`bot.handlers.profile`) — роутер не дублирует правила, только валидирует initData и мапит
результат в pydantic-схему (см. CLAUDE.md, «Mini App»).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel

from api.schemas import AbsolutesOut, AbsoluteOut
from api.auth import get_current_user_id
from api.db import get_session
from api.bot_info import get_bot_link
from api.deps import get_redis
from api.schemas import ActivePotionOut, CityOut, CountryOut, DevItemOut, PhaseProgressOut, ProfileOut, StatOut
from bot.config.clan import CLAN_DONATE_LEVELS, CLAN_MAX_MEMBERS
from bot.services import donate as donate_service
from bot.services.business import get_wallet
from bot.services.clan import clan_power, member_of
from bot.services.clan import view as clan_view
from bot.services.profile import DevItem, get_extras, get_profile
from bot.texts.bloodline import BLOODLINE_NAMES
from bot.texts.genius import GENIUS_NAMES
from bot.texts.profile import PHASE_LABELS, POTENTIAL_LABELS, STAT_LABELS
from bot.texts.unique_path import PATH_NAMES
from bot.texts.unique_technique import TECHNIQUE_NAMES

router = APIRouter(prefix="/api", tags=["profile"])

_TARGET_LABELS = {"circle": "Круг", "fist": "Кулак"}
_SCOPE_LABELS = {"city": "районов города", "country": "районов страны"}


def plain(name: str) -> str:
    """Название из бот-текстов без ведущего эмодзи («💪 Сила» -> «Сила»): в UI Mini App иконки — lucide."""
    head, _, tail = name.partition(" ")
    return tail if tail and not any(ch.isalnum() for ch in head) else name


def _dev(kind: str, names: dict[str, str], item: DevItem | None, suffix: str = "") -> DevItemOut | None:
    if item is None:
        return None
    return DevItemOut(label=plain(names.get(item.code, item.code)) + suffix, level=item.level, kind=kind)


async def _absolutes(session: AsyncSession, user_id: int) -> AbsolutesOut:
    """Абсолюты игрока и их перки; блок Ариана — сколько ещё не работают."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from bot.config.card import CARD_BY_CODE
    from bot.db.models.card_stack import CardStack
    from bot.db.models.user import User
    from bot.services.absolute import owned
    from bot.texts.absolute import PERKS

    codes = await owned(session, user_id)
    cards = set(await session.scalars(select(CardStack.card_code).where(CardStack.user_id == user_id, CardStack.card_code.in_(codes), CardStack.quantity > 0)))
    blocked = await session.scalar(select(User.absolute_blocked_until).where(User.id == user_id))
    left = max(0, int((blocked - datetime.now(timezone.utc)).total_seconds())) if blocked else 0
    return AbsolutesOut(
        items=[AbsoluteOut(code=c, name=CARD_BY_CODE[c].name, perk=PERKS.get(c, ""), via_stylist=c not in cards) for c in sorted(codes)],
        blocked_seconds=left,
    )


async def _potions(session: AsyncSession, user_id: int) -> list[ActivePotionOut]:
    """Действующие зелья — тот же расчёт, что экран зелий бота (`services.potion.catalog`)."""
    from bot.config.potion import POTION_EFFECTS
    from bot.constant.potion import POTIONS
    from bot.services.potion import catalog
    from bot.texts.development import describe_level
    from bot.texts.potion import POTION_NAMES, ROMAN

    active = sorted((s for s in (await catalog(session, user_id)).states.values() if s.tier), key=lambda s: POTIONS.index(s.kind))
    return [
        ActivePotionOut(
            name=plain(POTION_NAMES[s.kind]), tier=ROMAN[s.tier], left_seconds=s.left_seconds,
            effect=plain(describe_level(POTION_EFFECTS[s.kind][1][s.tier - 1])),
        )
        for s in active
    ]


@router.get("/profile", response_model=ProfileOut)
async def get_my_profile(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> ProfileOut:
    profile = await get_profile(session, user_id)
    if profile is None or not profile.is_onboarded:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Player not registered — open the bot and press /start first"
        )

    bl = profile.bloodline
    extras = await get_extras(
        session,
        redis,
        user_id,
        phase=profile.phase,
        city_id=profile.city.id if profile.city else None,
        bloodline=DevItem(bl.code, bl.level) if bl and bl.code else None,
    )
    pp = extras.phase_progress
    from bot.services.characteristic import potential_progress

    pot = await potential_progress(session, user_id)
    development = [
        _dev("bloodline", BLOODLINE_NAMES, extras.bloodline),
        _dev("bloodline", BLOODLINE_NAMES, extras.bloodline2, " (2)"),
        _dev("path", PATH_NAMES, extras.path),
        _dev("path", PATH_NAMES, extras.path2, " (2)"),
        _dev("technique", TECHNIQUE_NAMES, extras.technique),
        _dev("genius", GENIUS_NAMES, extras.genius),
    ]
    return ProfileOut(
        user_id=profile.user_id,
        username=profile.username,
        display_name=profile.display_name,
        is_onboarded=profile.is_onboarded,
        country=CountryOut(code=profile.country.code, name=profile.country.name) if profile.country else None,
        city=CityOut(id=profile.city.id, name=profile.city.name, district_count=profile.city.district_count)
        if profile.city
        else None,
        phase=profile.phase,
        phase_label=PHASE_LABELS.get(profile.phase, profile.phase),
        potential_label=POTENTIAL_LABELS.get(profile.stats.potential, profile.stats.potential),
        potential_points=pot.points, potential_cost=pot.cost,
        potential_next=POTENTIAL_LABELS.get(pot.next_potential) if pot.next_potential else None,
        gang_name=profile.gang_name,
        army_power=profile.army_power,
        attack_power=extras.attack_power,
        defense_power=extras.defense_power,
        districts=profile.districts,
        influence=profile.influence,
        nh_coins=profile.nh_coins,
        nh_coins_pending=profile.nh_coins_pending,
        donate_balance=extras.donate_balance,
        tickets=profile.tickets.count,
        tickets_cap=profile.tickets.cap,
        online=extras.online,
        avatar=extras.avatar_image,
        stats=[StatOut(code=s.code, label=plain(STAT_LABELS[s.code]), rank=s.rank) for s in profile.stats.stats],
        dev_points=profile.stats.dev_points,
        phase_progress=PhaseProgressOut(
            target_label=_TARGET_LABELS.get(pp.target_phase, pp.target_phase),
            scope_label=_SCOPE_LABELS[pp.scope],
            current=pp.current,
            total=pp.total,
        )
        if pp
        else None,
        development=[d for d in development if d is not None],
        second_body=extras.second_body,
        potions=await _potions(session, user_id),
        absolutes=await _absolutes(session, user_id),
        clan_name=profile.clan_name,
    )


class MoreClanOut(BaseModel):
    name: str
    members: int
    max_members: int
    donate_level: int
    max_donate_level: int
    lands: int
    power: int


class MoreOut(BaseModel):
    clan: MoreClanOut | None
    donate_balance: int
    income_per_minute: float
    income_pending: int
    bot_link: str | None
    is_admin: bool = False  # плитка «Админ-панель» — только сотрудникам (роль в админке)


@router.get("/more", response_model=MoreOut)
async def get_more(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> MoreOut:
    wallet = await get_wallet(session, user_id)
    if wallet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not registered")
    clan_out = None
    member = await member_of(session, user_id)
    if member is not None:
        view = await clan_view(session, member.clan_id)
        if view is not None:
            clan_out = MoreClanOut(
                name=view.clan.name,
                members=view.members,
                max_members=CLAN_MAX_MEMBERS,
                donate_level=view.clan.donate_level,
                max_donate_level=len(CLAN_DONATE_LEVELS),
                lands=view.clan.lands,
                power=await clan_power(session, view.clan.id),
            )
    return MoreOut(
        clan=clan_out,
        donate_balance=await donate_service.balance(session, user_id),
        income_per_minute=round(wallet.per_minute, 1),
        income_pending=wallet.pending,
        bot_link=await get_bot_link(),
        is_admin=await _is_staff(session, user_id),
    )


async def _is_staff(session: AsyncSession, user_id: int) -> bool:
    from bot.services.admin.roles import role_of

    return await role_of(session, user_id) is not None



@router.post("/potential-up")
async def post_potential_up(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    """Повысить потенциал за очки потенциала (2026-10-28) — тот же сервис, что кнопка в боте."""
    from bot.services.characteristic import NotEnoughPotentialPointsError, PotentialMaxedError, upgrade_potential

    try:
        new = await upgrade_potential(session, user_id)
    except PotentialMaxedError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Потенциал уже на максимуме.") from None
    except NotEnoughPotentialPointsError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Не хватает очков потенциала: нужно {exc.cost}, есть {exc.have}.") from None
    return {"ok": True, "message": f"Потенциал повышен: {POTENTIAL_LABELS.get(new, new)}!"}
