"""Карта страны в Mini App (круг и император): города страны, экран города, штурм ботов города
и вызов игрока за все его районы в городе. Логика — `services/district` (та же, что у карты
страны бота), пуши второй стороне и итоги трона/освобождения — те же функции бота."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers._common import plain_lines
from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad, clean_label, cooldown_text, require_user, telegram_bot, ttl_seconds
from bot.cache.keys import battle_cooldown
from bot.constant.settings import NOTIFY_PVP_CALL
from bot.handlers.district.district import _notify_liberations, _notify_throne, _window
from bot.keyboards.district import accept_menu
from bot.services.district import (
    BattleOnCooldownError,
    CityAlreadyChallengedError,
    CityNotInCountryError,
    EmperorNoConquestError,
    NoAttackersError,
    NoBotsInCityError,
    NotCityConquerorError,
    NothingToTakeError,
    OutgoingChallengeExistsError,
    attack_city_bots,
    get_city_owners,
    get_country_map,
    get_influence,
    issue_city_challenge,
)
from bot.services.extra import get_army_stats
from bot.services.phase import is_city_conqueror, is_emperor
from bot.services.settings import notify_player
from bot.texts.district import (
    CITY_ALREADY_CHALLENGED,
    CITY_CHALLENGE_INCOMING,
    CITY_CHALLENGE_SENT,
    CITY_NOT_FOUND,
    EMPEROR_NO_CONQUEST,
    NO_ATTACKERS,
    NO_BOTS_IN_CITY,
    NOT_CITY_CONQUEROR,
    NOTHING_TO_TAKE,
    OUTGOING_CHALLENGE_EXISTS,
    PROMOTED,
)
from bot.utils.formatting import esc, format_number

router = APIRouter(prefix="/api/country", tags=["country"])
BATTLE_PREFIX = "Сражение"


class CountryCityOut(BaseModel):
    id: int
    name: str
    districts: int
    bots: int
    mine: int
    owners: int
    fully_mine: bool


class ThroneStatusOut(BaseModel):
    can_challenge: bool  # круг держит все районы страны, а её города у императора(ов)
    missing: int  # сколько районов страны ещё не его
    has_emperor: bool  # у страны есть император / чужие держатели


class CountryOut(BaseModel):
    available: bool  # карта страны — у круга и императора; банда воюет за районы своего города
    country: str | None
    emperor: bool
    influence: int
    cities_mine: int
    cities: list[CountryCityOut]
    throne: ThroneStatusOut | None = None


@router.get("", response_model=CountryOut)
async def get_country(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> CountryOut:
    user = await require_user(session, user_id)
    if not is_city_conqueror(user.phase):
        return CountryOut(available=False, country=None, emperor=False, influence=0, cities_mine=0, cities=[])
    cm = await get_country_map(session, user)
    from bot.services.district import throne_status

    ts = await throne_status(session, user_id)
    return CountryOut(
        throne=ThroneStatusOut(can_challenge=ts.can_challenge, missing=ts.missing, has_emperor=bool(ts.incumbent_id or ts.foreign_holders)),
        available=True, country=clean_label(cm.country_name), emperor=is_emperor(user.phase),
        influence=await get_influence(session, user_id), cities_mine=cm.cities_mine,
        cities=[
            CountryCityOut(id=c.city_id, name=c.name, districts=c.district_count, bots=c.bots, mine=c.mine,
                           owners=c.owners, fully_mine=c.fully_mine)
            for c in cm.cities
        ],
    )


class CityOwnerOut(BaseModel):
    owner_id: int
    label: str
    districts: int
    is_mine: bool
    challenged: bool


class CityOut(BaseModel):
    id: int
    name: str
    districts: int
    bots: int
    bot_quantity: int
    bot_rank: str | None
    bot_power: int
    owners: list[CityOwnerOut]
    attack_quantity: int
    attack_power: int
    emperor: bool  # императору захват своей страны недоступен — кнопок нет
    cooldown_seconds: int


@router.get("/city/{city_id}", response_model=CityOut)
async def get_city_view(
    city_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> CityOut:
    user = await require_user(session, user_id)
    try:
        v = await get_city_owners(session, user, city_id)
    except (CityNotInCountryError, NotCityConquerorError):
        raise bad(clean_label(CITY_NOT_FOUND))
    army = await get_army_stats(session, user_id)
    return CityOut(
        id=v.city_id, name=v.name, districts=v.district_count, bots=v.bots, bot_quantity=v.bot_quantity,
        bot_rank=v.bot_rank, bot_power=v.bot_power,
        owners=[CityOwnerOut(owner_id=o.owner_id, label=o.label, districts=o.districts, is_mine=o.is_mine, challenged=o.challenged) for o in v.owners],
        attack_quantity=army.attack.quantity, attack_power=army.attack.power, emperor=is_emperor(user.phase),
        cooldown_seconds=await ttl_seconds(redis, battle_cooldown(user_id)),
    )


def _errors(exc: Exception):
    table = {
        EmperorNoConquestError: EMPEROR_NO_CONQUEST, NotCityConquerorError: NOT_CITY_CONQUEROR, CityNotInCountryError: CITY_NOT_FOUND,
        NoBotsInCityError: NO_BOTS_IN_CITY, NoAttackersError: NO_ATTACKERS, NothingToTakeError: NOTHING_TO_TAKE,
        OutgoingChallengeExistsError: OUTGOING_CHALLENGE_EXISTS, CityAlreadyChallengedError: CITY_ALREADY_CHALLENGED,
    }
    if isinstance(exc, BattleOnCooldownError):
        return bad(cooldown_text(BATTLE_PREFIX, exc.retry_after_seconds))
    return bad(clean_label(table[type(exc)]))


_CITY_ERRORS = (
    EmperorNoConquestError, NotCityConquerorError, CityNotInCountryError, NoBotsInCityError, NoAttackersError,
    NothingToTakeError, OutgoingChallengeExistsError, CityAlreadyChallengedError, BattleOnCooldownError,
)


class CityBattleOut(BaseModel):
    message: str
    won: bool
    captured: int
    city: str
    rounds: int
    attacker_quantity: int
    attacker_power: int
    attacker_dead: int
    attacker_fled: int
    attacker_remaining_power: int
    defender_power: int
    defender_dead: int
    influence: int
    promoted: str | None
    free_attack: bool
    journal: list[str] = []


@router.post("/city/{city_id}/attack-bots", response_model=CityBattleOut)
async def post_attack_bots(
    city_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> CityBattleOut:
    user = await require_user(session, user_id)
    try:
        r = await attack_city_bots(session, redis, user, city_id)
    except _CITY_ERRORS as exc:
        raise _errors(exc)
    if r.throne is not None or r.liberations:
        async with telegram_bot() as bot:
            await _notify_throne(bot, session, r.throne)
            await _notify_liberations(bot, session, r.liberations)
    if r.captured:
        message = f"Победа! Боты города {r.city_name} разбиты — районов стало больше на {r.captured}."
    elif r.won:
        message = f"Боты города {r.city_name} разбиты, но их районы уже успели захватить другие."
    else:
        message = f"Поражение: боты удержали город {r.city_name}."
    if r.throne is not None:
        message += " Трон: победа!" if r.throne.contender_won else f" Трон: поражение от «{r.throne.incumbent_label}»."
    for lib in r.liberations:
        message += (
            f" Освобождение: победа над «{lib.holder_label}», вернул городов {len(lib.city_names)}."
            if lib.contender_won else f" Освобождение: поражение от «{lib.holder_label}»."
        )
    return CityBattleOut(
        message=message, won=r.won, captured=r.captured, city=r.city_name, rounds=r.rounds,
        attacker_quantity=r.attacker_quantity, attacker_power=r.attacker_power, attacker_dead=r.attacker_dead,
        attacker_fled=r.attacker_fled, attacker_remaining_power=r.attacker_remaining_power,
        defender_power=r.defender_power, defender_dead=r.defender_dead, influence=r.influence,
        promoted=clean_label(PROMOTED[r.promoted_to]) if r.promoted_to else None, free_attack=r.free_attack,
        journal=plain_lines(r.journal),
    )


class ChallengeIn(BaseModel):
    owner_id: int


class MessageOut(BaseModel):
    message: str


@router.post("/city/{city_id}/challenge", response_model=MessageOut)
async def post_city_challenge(
    city_id: int,
    body: ChallengeIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> MessageOut:
    user = await require_user(session, user_id)
    try:
        issued = await issue_city_challenge(session, redis, user, city_id, body.owner_id)
    except _CITY_ERRORS as exc:
        raise _errors(exc)
    window = _window(issued.accept_seconds)
    incoming = CITY_CHALLENGE_INCOMING.format(
        city=issued.city_name, count=issued.districts, attacker=esc(issued.attacker_label), window=window,
        att_quantity=format_number(issued.defender_attack.quantity), att_power=format_number(issued.defender_attack.power),
        def_quantity=format_number(issued.defender_defense.quantity), def_power=format_number(issued.defender_defense.power),
    )
    async with telegram_bot() as bot:
        await notify_player(bot, session, issued.defender_id, NOTIFY_PVP_CALL, incoming, reply_markup=accept_menu(issued.challenge_id))
    sent = CITY_CHALLENGE_SENT.format(owner=issued.defender_label, window=window, city=issued.city_name, count=issued.districts)
    return MessageOut(message=clean_label(sent).replace("Итог придёт сюда.", "Итог придёт в чат с ботом."))



class ThroneBattleOut(BaseModel):
    message: str
    crowned: bool
    won: bool


@router.post("/throne", response_model=ThroneBattleOut)
async def post_throne(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> ThroneBattleOut:
    """Бой за трон по кнопке (2026-10-20) — те же бои за освобождение и трон, что после захвата,
    закрывшего страну; круг, державший всю страну, больше не застревает после проигрыша."""
    from api.push import get_bot
    from bot.constant.phase import PHASE_FIST
    from bot.handlers.district.district import _notify_liberations, _notify_throne
    from bot.services.district import BattleOnCooldownError, NoThroneTargetError, NotThroneContenderError, challenge_throne
    from bot.texts.map import THRONE_NO_TARGET, THRONE_NOT_CONTENDER, THRONE_NOT_CONTENDER_MISSING

    await require_user(session, user_id)
    try:
        promoted, throne, liberations = await challenge_throne(session, redis, user_id)
    except NotThroneContenderError as exc:
        raise bad(THRONE_NOT_CONTENDER_MISSING.format(missing=exc.missing) if exc.missing else THRONE_NOT_CONTENDER)
    except NoThroneTargetError:
        raise bad(THRONE_NO_TARGET)
    except BattleOnCooldownError as exc:
        raise bad(cooldown_text(BATTLE_PREFIX, exc.retry_after_seconds))
    parts = []
    for lib in liberations:
        parts.append(
            f"Освобождение: победа над «{lib.holder_label}», вернул городов {len(lib.city_names)}."
            if lib.contender_won else f"Освобождение: поражение от «{lib.holder_label}» — ты остаёшься кругом."
        )
    if throne is not None:
        parts.append(
            f"Бой за трон: победа над «{throne.incumbent_label}» за {throne.rounds} раунд."
            if throne.contender_won else f"Бой за трон: поражение от «{throne.incumbent_label}»."
        )
    crowned = promoted == PHASE_FIST
    if crowned:
        parts.append("Ты — император страны!")
    bot = get_bot()
    await _notify_liberations(bot, session, liberations)
    await _notify_throne(bot, session, throne)
    won = crowned or bool(liberations and all(lib.contender_won for lib in liberations) and (throne is None or throne.contender_won))
    return ThroneBattleOut(message=" ".join(parts) or "Бой окончен.", crowned=crowned, won=won)
