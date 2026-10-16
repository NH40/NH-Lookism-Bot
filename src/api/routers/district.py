"""API-роутер Mini App: район — карточка, атака на ботов, вызов игрока.

Те же сервисы, что хендлеры `bot.handlers.district` (`services.district.attack_district` /
`issue_challenge`). Защитнику вызова уходит тот же пуш с кнопкой «Принять бой», что и из бота.
Круг и выше воюют за город целиком — это остаётся в боте (сервис отдаёт `CityConquerorError`).
"""
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
from bot.config.game import CHALLENGE_ACCEPT_SECONDS
from bot.constant.district import SCOPE_CITY
from bot.constant.phase import PHASE_GANG
from bot.handlers.district.district import _notify_liberations, _notify_throne
from bot.keyboards.district import accept_menu
from bot.services.characteristic import get_combat_profile
from bot.services.district import (
    BattleOnCooldownError,
    BotDistrictError,
    CityConquerorError,
    DistrictAlreadyChallengedError,
    DistrictNotFoundError,
    EmperorNoConquestError,
    NoAttackersError,
    NotYourCityError,
    OutgoingChallengeExistsError,
    OwnDistrictError,
    PlayerDistrictError,
    attack_district,
    get_district_view,
    issue_challenge,
)
from bot.services.extra import get_army_stats
from bot.services.settings import notify_player
from bot.constant.settings import NOTIFY_PVP_CALL
from bot.texts.district import (
    CHALLENGE_INCOMING,
    CITY_CONQUEROR,
    DISTRICT_ALREADY_CHALLENGED,
    EMPEROR_NO_CONQUEST,
    NO_ATTACKERS,
    NOT_FOUND,
    OUTGOING_CHALLENGE_EXISTS,
    OWN_DISTRICT,
    PROMOTED,
    WINDOW_MINUTES,
)
from bot.utils.formatting import esc, format_number

router = APIRouter(prefix="/api/district", tags=["district"])

BATTLE_PREFIX = "Сражение"


class DistrictCardOut(BaseModel):
    id: int
    number: int
    kind: str  # mine | bot | player
    owner: str | None
    challenged: bool
    bot_rank: str | None
    bot_quantity: int | None
    bot_power: int | None
    attack_quantity: int
    attack_power: int
    accept_window_minutes: int
    can_act: bool
    blocked_reason: str | None
    cooldown_seconds: int


class ThroneOut(BaseModel):
    contender_won: bool
    incumbent: str
    rounds: int


class BattleOut(BaseModel):
    message: str
    won: bool
    captured: bool
    taken_by_other: bool
    district_number: int
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
    throne: ThroneOut | None
    journal: list[str] = []  # ход боя: шпионы, раунды, сработавшие навыки


class ChallengeOut(BaseModel):
    message: str
    district_number: int
    defender: str
    accept_window_minutes: int


@router.get("/{district_id}", response_model=DistrictCardOut)
async def district_card(
    district_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> DistrictCardOut:
    user = await require_user(session, user_id)
    try:
        view = await get_district_view(session, user, district_id)
    except DistrictNotFoundError:
        raise bad(NOT_FOUND)
    army = await get_army_stats(session, user.id)
    window = (await get_combat_profile(session, user.id)).accept_window(CHALLENGE_ACCEPT_SECONDS)
    reason = None
    if view.is_mine:
        reason = "Этот район уже твой."
    elif user.phase != PHASE_GANG:
        reason = "Круг и выше воюют за город целиком — это доступно в боте (Карта)."
    elif view.challenged:
        reason = "На этот район уже брошен вызов — дождись итога."
    elif army.attack.quantity <= 0:
        reason = "В лагере атаки нет бойцов — заверби или переведи из защиты."
    return DistrictCardOut(
        id=view.id, number=view.number,
        kind="mine" if view.is_mine else "bot" if view.owner_id is None else "player",
        owner=view.owner_label, challenged=view.challenged,
        bot_rank=view.bot_rank, bot_quantity=view.bot_quantity, bot_power=view.bot_power,
        attack_quantity=army.attack.quantity, attack_power=army.attack.power,
        accept_window_minutes=max(1, round(window / 60)),
        can_act=reason is None, blocked_reason=reason,
        cooldown_seconds=await ttl_seconds(redis, battle_cooldown(user.id)),
    )


@router.post("/{district_id}/attack", response_model=BattleOut)
async def attack(
    district_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> BattleOut:
    user = await require_user(session, user_id)
    try:
        report = await attack_district(session, redis, user, district_id)
    except PlayerDistrictError:
        raise bad("Этот район держит игрок — брось ему вызов.")
    except (DistrictNotFoundError, NotYourCityError):
        raise bad(NOT_FOUND)
    except OwnDistrictError:
        raise bad(OWN_DISTRICT)
    except EmperorNoConquestError:
        raise bad(EMPEROR_NO_CONQUEST)
    except CityConquerorError:
        raise bad(CITY_CONQUEROR)
    except NoAttackersError:
        raise bad(NO_ATTACKERS)
    except BattleOnCooldownError as exc:
        raise bad(cooldown_text(BATTLE_PREFIX, exc.retry_after_seconds))

    if report.throne is not None or report.liberations:
        async with telegram_bot() as bot:
            await _notify_throne(bot, session, report.throne)
            await _notify_liberations(bot, session, report.liberations)

    if report.captured:
        message = f"Район №{report.district_number} захвачен!"
    elif report.taken_by_other:
        message = f"Боты разбиты, но район №{report.district_number} успел забрать другой игрок."
    else:
        message = f"Поражение: район №{report.district_number} остался у ботов."
    for lib in report.liberations:  # бои за освобождение страны с чужими императорами
        message += (
            f" Освобождение: победа над «{lib.holder_label}», вернул городов {len(lib.city_names)}."
            if lib.contender_won else f" Освобождение: поражение от «{lib.holder_label}» — ты остаёшься кругом."
        )
    return BattleOut(
        message=message, won=report.won, captured=report.captured, taken_by_other=report.taken_by_other,
        district_number=report.district_number, rounds=report.rounds,
        attacker_quantity=report.attacker_quantity, attacker_power=report.attacker_power,
        attacker_dead=report.attacker_dead, attacker_fled=report.attacker_fled,
        attacker_remaining_power=report.attacker_remaining_power, defender_power=report.defender_power,
        defender_dead=report.defender_dead, influence=report.influence,
        promoted=clean_label(PROMOTED[report.promoted_to]) if report.promoted_to else None,
        free_attack=report.free_attack,
        journal=plain_lines(report.journal),
        throne=ThroneOut(
            contender_won=report.throne.contender_won, incumbent=report.throne.incumbent_label,
            rounds=report.throne.rounds,
        ) if report.throne else None,
    )


@router.post("/{district_id}/challenge", response_model=ChallengeOut)
async def challenge(
    district_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> ChallengeOut:
    user = await require_user(session, user_id)
    try:
        issued = await issue_challenge(session, redis, user, district_id)
    except (DistrictNotFoundError, NotYourCityError, BotDistrictError):
        raise bad(NOT_FOUND)
    except OwnDistrictError:
        raise bad(OWN_DISTRICT)
    except EmperorNoConquestError:
        raise bad(EMPEROR_NO_CONQUEST)
    except CityConquerorError:
        raise bad(CITY_CONQUEROR)
    except NoAttackersError:
        raise bad(NO_ATTACKERS)
    except BattleOnCooldownError as exc:
        raise bad(cooldown_text(BATTLE_PREFIX, exc.retry_after_seconds))
    except OutgoingChallengeExistsError:
        raise bad(OUTGOING_CHALLENGE_EXISTS)
    except DistrictAlreadyChallengedError:
        raise bad(DISTRICT_ALREADY_CHALLENGED)

    minutes = max(1, round(issued.accept_seconds / 60))
    window = WINDOW_MINUTES.format(minutes=minutes)
    # Защитнику — тот же пуш с кнопкой «Принять бой», что при вызове из бота (район; вызов за
    # город из Mini App не бросается).
    if issued.scope != SCOPE_CITY:
        incoming = CHALLENGE_INCOMING.format(
            number=issued.district_number, attacker=esc(issued.attacker_label), window=window,
            att_quantity=format_number(issued.defender_attack.quantity),
            att_power=format_number(issued.defender_attack.power),
            def_quantity=format_number(issued.defender_defense.quantity),
            def_power=format_number(issued.defender_defense.power),
        )
        async with telegram_bot() as bot:
            await notify_player(
                bot, session, issued.defender_id, NOTIFY_PVP_CALL, incoming,
                reply_markup=accept_menu(issued.challenge_id),
            )
    return ChallengeOut(
        message=f"Вызов брошен: район №{issued.district_number}, владелец {issued.defender_label}. "
        f"У него {window} на принятие боя, иначе бой пройдёт против его лагеря защиты.",
        district_number=issued.district_number, defender=issued.defender_label, accept_window_minutes=minutes,
    )
