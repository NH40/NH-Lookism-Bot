"""Районы — карточка района, атака на ботов, PvP-вызов (хендлеры).

Кнопка атаки одна на оба случая: район у ботов — бой сразу (`attack_district`), район
игрока — вызов (`issue_challenge`, защитнику уведомление с кнопкой "Принять бой").
Круг и выше воюют за город целиком (подтверждено 2026-09-29): бой с ботами всего города
(`attack_city_bots`) и вызов за все районы игрока в городе (`issue_city_challenge`) —
кнопки на экране города (`handlers/map`). `send_pvp_reports()` — публичная функция домена: итог PvP-боя обоим игрокам, её
переиспользует фоновый sweep просроченных вызовов (`main.py`). Шпионаж/разведка перед
боем (нужны шпион/разведчик в составе банды — уникальных персонажей ещё нет) — позже.
"""
from __future__ import annotations

from bot.services.position_skill import journal_block
from bot.constant.settings import NOTIFY_WAR_REPORT
from bot.texts.district import (
    LIBERATION_HOLDER_DEMOTED,
    LIBERATION_HOLDER_LOST,
    LIBERATION_HOLDER_WON,
    LIBERATION_LOST,
    LIBERATION_SPOILS_BUSINESSES,
    LIBERATION_SPOILS_TREASURY,
    LIBERATION_WON,
)
from bot.keyboards.common import back_menu
from bot.constant.map import CB_MAP_OPEN

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.game import CHALLENGE_ACCEPT_SECONDS
from bot.constant.district import (
    CB_CHALLENGE_ACCEPT_PREFIX,
    CB_CITY_ATTACK_BOTS_PREFIX,
    CB_CITY_CHALLENGE_PREFIX,
    CB_DISTRICT_ATTACK_PREFIX,
    CB_DISTRICT_VIEW_PREFIX,
    RESOLUTION_ACCEPTED,
    RESOLUTION_VOID,
    SCOPE_CITY,
)
from bot.db.models.user import User
from bot.db.repositories.user import get_by_id
from bot.keyboards.district import accept_menu, city_report_menu, district_menu, report_menu
from bot.services.district import (
    BattleOnCooldownError,
    BotDistrictError,
    ChallengeIssued,
    ChallengeNotFoundError,
    ChallengeOutcome,
    CityAlreadyChallengedError,
    CityConquerorError,
    CityNotInCountryError,
    DistrictAlreadyChallengedError,
    NoBotsInCityError,
    ThroneOutcome,
    NotCityConquerorError,
    NothingToTakeError,
    DistrictNotFoundError,
    EmperorNoConquestError,
    NoAttackersError,
    NotYourCityError,
    OutgoingChallengeExistsError,
    OwnDistrictError,
    PlayerDistrictError,
    accept_challenge,
    attack_city_bots,
    attack_district,
    get_district_view,
    issue_challenge,
    issue_city_challenge,
)
from bot.services.characteristic import get_combat_profile
from bot.services.extra import get_army_stats
from bot.services.phase import is_city_conqueror
from bot.texts.district import (
    BATTLE_COOLDOWN,
    BTN_ATTACK,
    BTN_CHALLENGE,
    CARD_BOT,
    CARD_MINE,
    CARD_OTHER,
    CARD_OTHER_CHALLENGED,
    CHALLENGE_GONE,
    CHALLENGE_INCOMING,
    CHALLENGE_SENT,
    CITY_ALREADY_CHALLENGED,
    CITY_CHALLENGE_INCOMING,
    CITY_CHALLENGE_SENT,
    CITY_CONQUEROR,
    CITY_NOT_FOUND,
    CITY_REPORT_HEADLINE_CAPTURED,
    CITY_REPORT_HEADLINE_LOST,
    CITY_REPORT_HEADLINE_TAKEN,
    DISTRICT_ALREADY_CHALLENGED,
    EMPEROR_NO_CONQUEST,
    FREE_ATTACK_LINE,
    HEADLINE_CAPTURED,
    HEADLINE_LOST,
    HEADLINE_TAKEN,
    HOW_ACCEPTED,
    HOW_TIMEOUT,
    NO_ATTACKERS,
    NO_BOTS_IN_CITY,
    NOT_CITY_CONQUEROR,
    NOT_FOUND,
    NOTHING_TO_TAKE,
    OUTGOING_CHALLENGE_EXISTS,
    OWN_DISTRICT,
    PROMOTED,
    PVP_ATTACKER_LOST,
    PVP_ATTACKER_WON,
    PVP_CITY_ATTACKER_LOST,
    PVP_CITY_ATTACKER_WON,
    PVP_CITY_DEFENDER_LOST,
    PVP_CITY_DEFENDER_WON,
    PVP_CITY_VOID,
    PVP_DEFENDER_LOST,
    PVP_DEFENDER_WON,
    PVP_REPORT,
    PVP_VOID,
    REPORT,
    THRONE_DEFENDED,
    THRONE_LOST,
    THRONE_TOPPLED,
    THRONE_WON,
    WINDOW_MINUTES,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.formatting import esc, format_countdown, format_number
from bot.services.settings import notify_player
from bot.constant.settings import NOTIFY_PVP_CALL, NOTIFY_PVP_REPORT, NOTIFY_THRONE
from bot.services.foresight import vs_bots as forecast_vs_bots, vs_player as forecast_vs_player
from bot.texts.foresight import forecast_line
from bot.utils.safe_edit import safe_clear_markup, safe_edit_text

router = Router(name="district")

def _throne_line(throne: ThroneOutcome | None) -> str:
    """Строка итога боя за трон в отчёт тому, кто закрыл страну."""
    if throne is None:
        return ""
    template = THRONE_WON if throne.contender_won else THRONE_LOST
    return template.format(
        incumbent=esc(throne.incumbent_label), rounds=throne.rounds,
        dead=format_number(throne.contender_dead), enemy_dead=format_number(throne.incumbent_dead),
    )


async def _notify_throne(bot: Bot, session: AsyncSession, throne: ThroneOutcome | None) -> None:
    """Пуш императору, на чей трон пошли (best-effort)."""
    if throne is None:
        return
    template = THRONE_TOPPLED if throne.contender_won else THRONE_DEFENDED
    await notify_player(
        bot, session, throne.incumbent_id, NOTIFY_THRONE,
        template.format(
            contender=esc(throne.contender_label), rounds=throne.rounds,
            dead=format_number(throne.incumbent_dead), enemy_dead=format_number(throne.contender_dead),
        ),
    )


def _liberation_lines(liberations) -> str:
    """Итоги боёв за освобождение страны — в отчёт тому, кто закрыл страну."""
    out = ""
    for lib in liberations:
        common = {
            "holder": esc(lib.holder_label), "rounds": lib.rounds,
            "dead": format_number(lib.contender_dead), "enemy_dead": format_number(lib.holder_dead),
        }
        if lib.contender_won:
            spoils = LIBERATION_SPOILS_TREASURY.format(amount=format_number(lib.treasury)) if lib.treasury else ""
            spoils += LIBERATION_SPOILS_BUSINESSES.format(count=lib.businesses) if lib.businesses else ""
            out += LIBERATION_WON.format(cities=esc(", ".join(lib.city_names)) or "—", spoils=spoils, **common)
        else:
            out += LIBERATION_LOST.format(**common)
    return out


async def _notify_liberations(bot: Bot, session: AsyncSession, liberations) -> None:
    """Пуш чужому императору, у которого освобождали страну (best-effort)."""
    for lib in liberations:
        common = {
            "contender": esc(lib.contender_label), "rounds": lib.rounds,
            "dead": format_number(lib.holder_dead), "enemy_dead": format_number(lib.contender_dead),
        }
        if lib.contender_won:
            extra = LIBERATION_SPOILS_TREASURY.format(amount=format_number(lib.treasury)) if lib.treasury else ""
            extra += LIBERATION_SPOILS_BUSINESSES.format(count=lib.businesses) if lib.businesses else ""
            extra += LIBERATION_HOLDER_DEMOTED if lib.holder_demoted else ""
            text = LIBERATION_HOLDER_LOST.format(cities=esc(", ".join(lib.city_names)) or "—", extra=extra, **common)
        else:
            text = LIBERATION_HOLDER_WON.format(**common)
        await notify_player(bot, session, lib.holder_id, NOTIFY_WAR_REPORT, text)


def _window(seconds: int) -> str:
    """Окно принятия вызова текстом — в минутах: оно зависит от Скорости нападающего
    (−1% за ранг), ровных часов больше нет."""
    return WINDOW_MINUTES.format(minutes=max(1, round(seconds / 60)))


async def _onboarded(session: AsyncSession, user_id: int) -> User | None:
    user = await get_by_id(session, user_id)
    return user if user is not None and user.city_id is not None else None


@router.callback_query(F.data.startswith(CB_DISTRICT_VIEW_PREFIX))
async def cb_district_view(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await _onboarded(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        view = await get_district_view(session, user, int(callback.data.removeprefix(CB_DISTRICT_VIEW_PREFIX)))
    except DistrictNotFoundError:
        await callback.answer(NOT_FOUND, show_alert=True)
        return

    if view.is_mine:
        text, action = CARD_MINE.format(number=view.number), None
    else:
        army = await get_army_stats(session, user.id)
        attack = {"attack_quantity": format_number(army.attack.quantity), "attack_power": format_number(army.attack.power)}
        if view.owner_id is None:
            text = CARD_BOT.format(
                number=view.number, quantity=format_number(view.bot_quantity), rank=view.bot_rank,
                power=format_number(view.bot_power), **attack,
            ) + forecast_line(await forecast_vs_bots(session, user.id, view.bot_rank, view.bot_quantity))
            action = BTN_ATTACK
        else:
            window = (await get_combat_profile(session, user.id)).accept_window(CHALLENGE_ACCEPT_SECONDS)
            text = CARD_OTHER.format(number=view.number, owner=esc(view.owner_label), window=_window(window), **attack)
            text += forecast_line(await forecast_vs_player(session, user.id, view.owner_id))
            if view.challenged:
                text += CARD_OTHER_CHALLENGED
            action = None if view.challenged else BTN_CHALLENGE
        if is_city_conqueror(user.phase):
            action = None

    await callback.answer()
    await safe_edit_text(
        callback.message, text,
        reply_markup=district_menu(
            view.id, view.number, action_label=action, is_mine=view.is_mine,
            scout_target=view.owner_id if view.owner_id and not view.is_mine else None,
        ),
    )


@router.callback_query(F.data.startswith(CB_DISTRICT_ATTACK_PREFIX))
async def cb_district_attack(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user = await _onboarded(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    district_id = int(callback.data.removeprefix(CB_DISTRICT_ATTACK_PREFIX))

    # Popup-тексты — без HTML (Telegram не парсит разметку в алертах).
    try:
        report = await attack_district(session, redis, user, district_id)
    except PlayerDistrictError:
        await _issue_challenge(callback, session, redis, user, district_id)
        return
    except (DistrictNotFoundError, NotYourCityError):
        await callback.answer(NOT_FOUND, show_alert=True)
        return
    except OwnDistrictError:
        await callback.answer(OWN_DISTRICT, show_alert=True)
        return
    except EmperorNoConquestError:
        await callback.answer(EMPEROR_NO_CONQUEST, show_alert=True)
        return
    except CityConquerorError:
        await callback.answer(CITY_CONQUEROR, show_alert=True)
        return
    except NoAttackersError:
        await callback.answer(NO_ATTACKERS, show_alert=True)
        return
    except BattleOnCooldownError as exc:
        await callback.answer(BATTLE_COOLDOWN.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
        return

    if report.captured:
        headline = HEADLINE_CAPTURED.format(number=report.district_number)
    elif report.taken_by_other:
        headline = HEADLINE_TAKEN.format(number=report.district_number)
    else:
        headline = HEADLINE_LOST.format(number=report.district_number)

    await callback.answer()
    await _notify_throne(callback.bot, session, report.throne)
    await _notify_liberations(callback.bot, session, report.liberations)
    await callback.message.answer(
        REPORT.format(
            headline=headline,
            rounds=report.rounds,
            att_quantity=format_number(report.attacker_quantity),
            att_power=format_number(report.attacker_power),
            att_dead=format_number(report.attacker_dead),
            att_fled=format_number(report.attacker_fled),
            att_remaining=format_number(report.attacker_remaining_power),
            def_power=format_number(report.defender_power),
            def_dead=format_number(report.defender_dead),
            influence=report.influence,
        )
        + (PROMOTED[report.promoted_to] if report.promoted_to else "")
        + (FREE_ATTACK_LINE if report.free_attack else "")
        + _throne_line(report.throne) + _liberation_lines(report.liberations)
        + journal_block(report.journal),
        # Проиграл — район всё ещё у ботов, можно пробовать снова (после КД).
        reply_markup=report_menu(district_id, report.district_number, can_attack_again=not report.won),
    )


async def _issue_challenge(
    callback: CallbackQuery, session: AsyncSession, redis: Redis, user: User, district_id: int
) -> None:
    try:
        issued = await issue_challenge(session, redis, user, district_id)
    except (DistrictNotFoundError, NotYourCityError, BotDistrictError):
        await callback.answer(NOT_FOUND, show_alert=True)
        return
    except OwnDistrictError:
        await callback.answer(OWN_DISTRICT, show_alert=True)
        return
    except EmperorNoConquestError:
        await callback.answer(EMPEROR_NO_CONQUEST, show_alert=True)
        return
    except CityConquerorError:
        await callback.answer(CITY_CONQUEROR, show_alert=True)
        return
    except NoAttackersError:
        await callback.answer(NO_ATTACKERS, show_alert=True)
        return
    except BattleOnCooldownError as exc:
        await callback.answer(BATTLE_COOLDOWN.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
        return
    except OutgoingChallengeExistsError:
        await callback.answer(OUTGOING_CHALLENGE_EXISTS, show_alert=True)
        return
    except DistrictAlreadyChallengedError:
        await callback.answer(DISTRICT_ALREADY_CHALLENGED, show_alert=True)
        return

    await callback.answer()
    await _announce_challenge(callback, session, issued)


async def _announce_challenge(callback: CallbackQuery, session: AsyncSession, issued: ChallengeIssued) -> None:
    """Нападающему — "вызов брошен", защитнику — пуш с кнопкой "Принять бой"; тексты по масштабу."""
    common = {"owner": esc(issued.defender_label), "window": _window(issued.accept_seconds)}
    army = {
        "attacker": esc(issued.attacker_label),
        "window": _window(issued.accept_seconds),
        "att_quantity": format_number(issued.defender_attack.quantity),
        "att_power": format_number(issued.defender_attack.power),
        "def_quantity": format_number(issued.defender_defense.quantity),
        "def_power": format_number(issued.defender_defense.power),
    }
    if issued.scope == SCOPE_CITY:
        sent = CITY_CHALLENGE_SENT.format(city=issued.city_name, count=issued.districts, **common)
        incoming = CITY_CHALLENGE_INCOMING.format(city=issued.city_name, count=issued.districts, **army)
    else:
        sent = CHALLENGE_SENT.format(number=issued.district_number, **common)
        incoming = CHALLENGE_INCOMING.format(number=issued.district_number, **army)
    await callback.message.answer(sent, reply_markup=back_menu(CB_MAP_OPEN))
    await notify_player(
        callback.bot, session, issued.defender_id, NOTIFY_PVP_CALL, incoming, reply_markup=accept_menu(issued.challenge_id)
    )


@router.callback_query(F.data.startswith(CB_CHALLENGE_ACCEPT_PREFIX))
async def cb_challenge_accept(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user = await get_by_id(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        outcome = await accept_challenge(session, redis, user, int(callback.data.removeprefix(CB_CHALLENGE_ACCEPT_PREFIX)))
    except ChallengeNotFoundError:
        await callback.answer(CHALLENGE_GONE, show_alert=True)
        await safe_clear_markup(callback.message)
        return

    await callback.answer()
    await safe_clear_markup(callback.message)
    await send_pvp_reports(callback.bot, session, outcome)


async def send_pvp_reports(bot: Bot, session: AsyncSession, outcome: ChallengeOutcome) -> None:
    """Итог PvP-вызова — каждому своя формулировка (нападающему "победа/поражение",
    защитнику "район удержан/потерян"). Доставка best-effort (`utils/notify`) — игрок мог
    заблокировать бота, бой к этому моменту уже закоммичен."""
    attacker, defender = esc(outcome.attacker_label), esc(outcome.defender_label)
    is_city = outcome.scope == SCOPE_CITY
    if outcome.resolution == RESOLUTION_VOID:
        void = (
            PVP_CITY_VOID.format(city=outcome.city_name, defender=defender)
            if is_city
            else PVP_VOID.format(number=outcome.district_number, defender=defender)
        )
        await notify_player(bot, session, outcome.attacker_id, NOTIFY_PVP_REPORT, void)
        return

    body = {
        "how": HOW_ACCEPTED if outcome.resolution == RESOLUTION_ACCEPTED else HOW_TIMEOUT,
        "rounds": outcome.rounds,
        "attacker": attacker,
        "defender": defender,
        "att_quantity": format_number(outcome.attacker_quantity),
        "att_power": format_number(outcome.attacker_power),
        "att_dead": format_number(outcome.attacker_dead),
        "att_fled": format_number(outcome.attacker_fled),
        "def_quantity": format_number(outcome.defender_quantity),
        "def_power": format_number(outcome.defender_power),
        "def_dead": format_number(outcome.defender_dead),
        "def_fled": format_number(outcome.defender_fled),
    }
    won = outcome.attacker_won and outcome.captured
    if is_city:
        where = {"city": outcome.city_name, "count": outcome.captured_districts}
        attacker_headline = (PVP_CITY_ATTACKER_WON if won else PVP_CITY_ATTACKER_LOST).format(defender=defender, **where)
        defender_headline = (PVP_CITY_DEFENDER_LOST if won else PVP_CITY_DEFENDER_WON).format(attacker=attacker, **where)
    else:
        number = outcome.district_number
        attacker_headline = (PVP_ATTACKER_WON if won else PVP_ATTACKER_LOST).format(number=number, defender=defender)
        defender_headline = (PVP_DEFENDER_LOST if won else PVP_DEFENDER_WON).format(number=number, attacker=attacker)
    promoted = PROMOTED[outcome.attacker_promoted_to] if outcome.attacker_promoted_to else ""
    promoted += FREE_ATTACK_LINE if outcome.free_attack else ""
    promoted += _throne_line(outcome.throne) + _liberation_lines(outcome.liberations)
    await _notify_throne(bot, session, outcome.throne)
    await _notify_liberations(bot, session, outcome.liberations)
    await notify_player(
        bot, session, outcome.attacker_id, NOTIFY_PVP_REPORT,
        PVP_REPORT.format(headline=attacker_headline, **body) + promoted + journal_block(outcome.journal),
    )
    await notify_player(
        bot, session, outcome.defender_id, NOTIFY_PVP_REPORT,
        PVP_REPORT.format(headline=defender_headline, **body) + journal_block(outcome.defender_journal),
    )


# --- круг: бой за город ---


@router.callback_query(F.data.startswith(CB_CITY_ATTACK_BOTS_PREFIX))
async def cb_city_attack_bots(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user = await _onboarded(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        city_id = int(callback.data.removeprefix(CB_CITY_ATTACK_BOTS_PREFIX))
        report = await attack_city_bots(session, redis, user, city_id)
    except ValueError:
        await callback.answer()
        return
    except EmperorNoConquestError:
        await callback.answer(EMPEROR_NO_CONQUEST, show_alert=True)
        return
    except NotCityConquerorError:
        await callback.answer(NOT_CITY_CONQUEROR, show_alert=True)
        return
    except CityNotInCountryError:
        await callback.answer(CITY_NOT_FOUND, show_alert=True)
        return
    except NoBotsInCityError:
        await callback.answer(NO_BOTS_IN_CITY, show_alert=True)
        return
    except NoAttackersError:
        await callback.answer(NO_ATTACKERS, show_alert=True)
        return
    except BattleOnCooldownError as exc:
        await callback.answer(BATTLE_COOLDOWN.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
        return

    if report.captured:
        headline = CITY_REPORT_HEADLINE_CAPTURED.format(city=report.city_name, count=report.captured)
    elif report.won:
        headline = CITY_REPORT_HEADLINE_TAKEN.format(city=report.city_name)
    else:
        headline = CITY_REPORT_HEADLINE_LOST.format(city=report.city_name)

    await callback.answer()
    await _notify_throne(callback.bot, session, report.throne)
    await _notify_liberations(callback.bot, session, report.liberations)
    await callback.message.answer(
        REPORT.format(
            headline=headline,
            rounds=report.rounds,
            att_quantity=format_number(report.attacker_quantity),
            att_power=format_number(report.attacker_power),
            att_dead=format_number(report.attacker_dead),
            att_fled=format_number(report.attacker_fled),
            att_remaining=format_number(report.attacker_remaining_power),
            def_power=format_number(report.defender_power),
            def_dead=format_number(report.defender_dead),
            influence=report.influence,
        )
        + (PROMOTED[report.promoted_to] if report.promoted_to else "")
        + (FREE_ATTACK_LINE if report.free_attack else "")
        + _throne_line(report.throne) + _liberation_lines(report.liberations)
        + journal_block(report.journal),
        reply_markup=city_report_menu(city_id, can_attack_again=not report.won),
    )


@router.callback_query(F.data.startswith(CB_CITY_CHALLENGE_PREFIX))
async def cb_city_challenge(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user = await _onboarded(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        city_raw, owner_raw = callback.data.removeprefix(CB_CITY_CHALLENGE_PREFIX).split(":")
        issued = await issue_city_challenge(session, redis, user, int(city_raw), int(owner_raw))
    except ValueError:
        await callback.answer()
        return
    except EmperorNoConquestError:
        await callback.answer(EMPEROR_NO_CONQUEST, show_alert=True)
        return
    except NotCityConquerorError:
        await callback.answer(NOT_CITY_CONQUEROR, show_alert=True)
        return
    except CityNotInCountryError:
        await callback.answer(CITY_NOT_FOUND, show_alert=True)
        return
    except NothingToTakeError:
        await callback.answer(NOTHING_TO_TAKE, show_alert=True)
        return
    except NoAttackersError:
        await callback.answer(NO_ATTACKERS, show_alert=True)
        return
    except BattleOnCooldownError as exc:
        await callback.answer(BATTLE_COOLDOWN.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
        return
    except OutgoingChallengeExistsError:
        await callback.answer(OUTGOING_CHALLENGE_EXISTS, show_alert=True)
        return
    except CityAlreadyChallengedError:
        await callback.answer(CITY_ALREADY_CHALLENGED, show_alert=True)
        return

    await callback.answer()
    await _announce_challenge(callback, session, issued)
