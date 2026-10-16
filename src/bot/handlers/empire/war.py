"""Война императоров — список целей, объявление, принятие боя, отчёты (хендлеры).

Вход — «⚔️ Война императоров» на экране «👑 Империя». `send_war_reports()` — публичная
функция домена: итог шлёт и хендлер принятия, и фоновый проход по неявкам (`main.py`).
"""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.position_skill import journal_block
from bot.config.empire import EMPIRE_WAR_ACCEPT_SECONDS, EMPIRE_WAR_COOLDOWN_SECONDS
from bot.constant.empire import (
    CB_WAR_ACCEPT_PREFIX,
    CB_WAR_DECLARE_PREFIX,
    CB_WAR_LIST_PREFIX,
    CB_WAR_TARGET_PREFIX,
    WAR_ACCEPTED,
    WAR_VOID,
)
from bot.keyboards.empire import war_accept_menu, war_target_menu, war_targets_menu
from bot.services.district import NoAttackersError
from bot.services.empire import (
    OutgoingWarExistsError,
    TargetAtWarError,
    TargetHasNoCitiesError,
    TargetNotEmperorError,
    TargetShieldedError,
    WarNotEmperorError,
    WarNotFoundError,
    WarOnCooldownError,
    WarOutcome,
    accept_war,
    declare_war,
    get_war_target,
    list_war_targets,
)
from bot.texts.district import NO_ATTACKERS
from bot.texts.empire import (
    BTN_WAR_TARGET,
    NO_WAR_TARGETS,
    OUTGOING_WAR_EXISTS_ALERT,
    PUSH_WAR_DECLARED,
    TARGET_AT_WAR_ALERT,
    TARGET_NO_CITIES_ALERT,
    TARGET_NOT_EMPEROR_ALERT,
    TARGET_SHIELDED_ALERT,
    WAR_ATTACKER_LOST,
    WAR_ATTACKER_WON,
    WAR_COOLDOWN_ALERT,
    WAR_DECLARED,
    WAR_DEFENDER_LOST,
    WAR_DEFENDER_WON,
    WAR_DEMOTED,
    WAR_HOW_ACCEPTED,
    WAR_HOW_FORFEIT,
    WAR_NOT_EMPEROR_ALERT,
    WAR_NOT_FOUND_ALERT,
    WAR_REPORT,
    WAR_SPOILS_CITIES,
    WAR_SPOILS_BUSINESSES,
    WAR_SPOILS_TREASURY,
    WAR_TARGET_SCREEN,
    WAR_TARGETS_SCREEN,
    WAR_VOID as WAR_VOID_TEXT,
)
from bot.utils.formatting import esc, format_countdown, format_number
from bot.services.settings import notify_player
from bot.constant.settings import NOTIFY_WAR_CALL, NOTIFY_WAR_REPORT
from bot.utils.safe_edit import safe_edit_text

router = Router(name="empire_war")


def _name(username: str | None, display_name: str | None) -> str:
    return f"@{username}" if username else (display_name or "—")


def _parse_int(raw: str) -> int | None:
    return int(raw) if raw.lstrip("-").isdigit() else None


@router.callback_query(F.data.startswith(CB_WAR_LIST_PREFIX))
async def cb_war_list(callback: CallbackQuery, session: AsyncSession) -> None:
    page = _parse_int(callback.data.removeprefix(CB_WAR_LIST_PREFIX)) or 0
    try:
        targets = await list_war_targets(session, callback.from_user.id, page)
    except WarNotEmperorError:
        await callback.answer(WAR_NOT_EMPEROR_ALERT, show_alert=True)
        return
    await callback.answer()
    buttons = [
        (
            t.user_id,
            BTN_WAR_TARGET.format(name=_name(t.username, t.display_name), country=t.country_name or "—", cities=t.cities),
        )
        for t in targets.items
    ]
    text = WAR_TARGETS_SCREEN + ("" if targets.items else NO_WAR_TARGETS)
    await safe_edit_text(callback.message, text, reply_markup=war_targets_menu(buttons, targets.page, targets.has_more))


@router.callback_query(F.data.startswith(CB_WAR_TARGET_PREFIX))
async def cb_war_target(callback: CallbackQuery, session: AsyncSession) -> None:
    target_id = _parse_int(callback.data.removeprefix(CB_WAR_TARGET_PREFIX))
    if target_id is None:
        await callback.answer()
        return
    try:
        target = await get_war_target(session, callback.from_user.id, target_id)
    except WarNotEmperorError:
        await callback.answer(WAR_NOT_EMPEROR_ALERT, show_alert=True)
        return
    except TargetNotEmperorError:
        await callback.answer(TARGET_NOT_EMPEROR_ALERT, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message,
        WAR_TARGET_SCREEN.format(
            name=esc(_name(target.username, target.display_name)),
            country=esc(target.country_name or "—"),
            cities=target.cities,
            coins=format_number(target.nh_coins),
            window=format_countdown(EMPIRE_WAR_ACCEPT_SECONDS),
            cooldown=format_countdown(EMPIRE_WAR_COOLDOWN_SECONDS),
        ),
        reply_markup=war_target_menu(target_id),
    )


@router.callback_query(F.data.startswith(CB_WAR_DECLARE_PREFIX))
async def cb_war_declare(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    target_id = _parse_int(callback.data.removeprefix(CB_WAR_DECLARE_PREFIX))
    if target_id is None:
        await callback.answer()
        return
    # Popup-тексты — без HTML.
    try:
        issued = await declare_war(session, redis, callback.from_user.id, target_id)
    except WarNotEmperorError:
        await callback.answer(WAR_NOT_EMPEROR_ALERT, show_alert=True)
        return
    except TargetNotEmperorError:
        await callback.answer(TARGET_NOT_EMPEROR_ALERT, show_alert=True)
        return
    except TargetHasNoCitiesError:
        await callback.answer(TARGET_NO_CITIES_ALERT, show_alert=True)
        return
    except TargetShieldedError as exc:
        await callback.answer(
            TARGET_SHIELDED_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True
        )
        return
    except NoAttackersError:
        await callback.answer(NO_ATTACKERS, show_alert=True)
        return
    except OutgoingWarExistsError:
        await callback.answer(OUTGOING_WAR_EXISTS_ALERT, show_alert=True)
        return
    except TargetAtWarError:
        await callback.answer(TARGET_AT_WAR_ALERT, show_alert=True)
        return
    except WarOnCooldownError as exc:
        await callback.answer(
            WAR_COOLDOWN_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True
        )
        return
    await callback.answer()
    target = await get_war_target(session, callback.from_user.id, target_id)
    window = format_countdown(issued.window_seconds)
    await safe_edit_text(
        callback.message,
        WAR_DECLARED.format(defender=esc(_name(target.username, target.display_name)), window=window),
        reply_markup=war_target_menu(target_id),
    )
    await notify_player(
        callback.bot,
        session,
        issued.defender_id,
        NOTIFY_WAR_CALL,
        PUSH_WAR_DECLARED.format(attacker=esc(issued.attacker_label), window=window),
        reply_markup=war_accept_menu(issued.war_id),
    )


@router.callback_query(F.data.startswith(CB_WAR_ACCEPT_PREFIX))
async def cb_war_accept(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    war_id = _parse_int(callback.data.removeprefix(CB_WAR_ACCEPT_PREFIX))
    if war_id is None:
        await callback.answer()
        return
    try:
        outcome = await accept_war(session, redis, callback.from_user.id, war_id)
    except WarNotFoundError:
        await callback.answer(WAR_NOT_FOUND_ALERT, show_alert=True)
        return
    await callback.answer()
    await send_war_reports(callback.bot, session, outcome)


async def send_war_reports(bot: Bot, session: AsyncSession, outcome: WarOutcome) -> None:
    """Итог войны — каждой стороне своя формулировка. Доставка best-effort (`utils/notify`)."""
    attacker, defender = esc(outcome.attacker_label), esc(outcome.defender_label)
    if outcome.resolution == WAR_VOID:
        await notify_player(bot, session, outcome.attacker_id, NOTIFY_WAR_REPORT, WAR_VOID_TEXT.format(defender=defender))
        return
    spoils = ""
    if outcome.city_names:
        spoils += WAR_SPOILS_CITIES.format(cities=", ".join(esc(n) for n in outcome.city_names))
    if outcome.treasury_taken:
        spoils += WAR_SPOILS_TREASURY.format(amount=format_number(outcome.treasury_taken), percent=outcome.treasury_percent)
    if outcome.businesses_taken:
        spoils += WAR_SPOILS_BUSINESSES.format(count=outcome.businesses_taken)
    if outcome.defender_demoted:
        spoils += WAR_DEMOTED.format(defender=defender)
    body = {
        "how": (
            WAR_HOW_ACCEPTED.format(rounds=outcome.rounds) if outcome.resolution == WAR_ACCEPTED else WAR_HOW_FORFEIT.format(rounds=outcome.rounds)
        ),
        "attacker": attacker,
        "defender": defender,
        "att_power": format_number(outcome.attacker_power),
        "att_dead": format_number(outcome.attacker_dead),
        "def_power": format_number(outcome.defender_power),
        "def_dead": format_number(outcome.defender_dead),
        "spoils": spoils,
    }
    won = outcome.attacker_won
    await notify_player(
        bot,
        session,
        outcome.attacker_id,
        NOTIFY_WAR_REPORT,
        WAR_REPORT.format(headline=(WAR_ATTACKER_WON if won else WAR_ATTACKER_LOST).format(defender=defender), **body)
        + journal_block(outcome.journal),
    )
    await notify_player(
        bot,
        session,
        outcome.defender_id,
        NOTIFY_WAR_REPORT,
        WAR_REPORT.format(headline=(WAR_DEFENDER_LOST if won else WAR_DEFENDER_WON).format(attacker=attacker), **body)
        + journal_block(outcome.defender_journal),
    )
