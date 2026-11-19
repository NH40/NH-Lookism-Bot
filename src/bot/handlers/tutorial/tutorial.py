"""Лига-обучение (хендлеры бота): экран шага, бои на учебной карте, кафе, доход, проверка шага."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.tutorial import TRAINING_POWER_DISTRICTS, TRAINING_STEPS
from bot.constant.tutorial import CB_TUT_ATTACK_PREFIX, CB_TUT_BUILD_PREFIX, CB_TUT_CHECK, CB_TUT_COLLECT, CB_TUT_OPEN, CB_TUT_START
from bot.keyboards.tutorial import back_menu, start_menu, tutorial_menu
from bot.services import tutorial as svc
from bot.texts.resource import amount_label
from bot.texts.tutorial import (
    BUILT,
    CD_LINE,
    CITY_LINE,
    COLLECTED,
    DONE_SCREEN,
    ERRORS,
    FIGHT_LOST,
    FIGHT_WON,
    GRADUATED,
    INCOME_LINE,
    INTRO_LEGACY,
    MAP_LINE_HINT,
    NOT_YET,
    NOTHING_TO_COLLECT,
    SCREEN,
    SEP,
    STEP_DONE,
    STEP_TEXTS,
    STEP_TITLES,
)
from bot.utils.formatting import format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="tutorial")


def error_text(exc: svc.TutorialError) -> str:
    return ERRORS.get(exc.code, exc.code).format(value=exc.value)


def reward_text(rewards: dict[str, int]) -> str:
    return ", ".join(amount_label(k, v) for k, v in rewards.items()) or "—"


def advance_text(adv: svc.Advance | None) -> str:
    if adv is None or not adv.done:
        return ""
    text = "\n".join(STEP_DONE.format(title=STEP_TITLES[c]) for c in adv.done) + f"\n🎁 {reward_text(adv.rewards)}"
    return text + (f"\n{GRADUATED}" if adv.finished else "")


def render_map(view: svc.TutorialView) -> str:
    lines = []
    for c in view.cities:
        districts = "".join(("🏠" if o else "🤖") for o in c.owned)
        built = sum(c.buildings)
        mark = "✅" if all(c.owned) else ("🔒" if not c.open else "⚔️")
        lock = "" if c.open else " · откроется после предыдущего"
        lines.append(CITY_LINE.format(mark=mark, name=c.name, owned=sum(c.owned), total=len(c.owned), lock=lock) + f"\n{districts}" + (f" · 🏪 {built}" if built else ""))
    return "\n".join(lines) + f"\n<i>{MAP_LINE_HINT}</i>"


async def render(session: AsyncSession, redis: Redis, user_id: int):
    view = await svc.view(session, redis, user_id)
    if view.status == svc.STATUS_DONE:
        return DONE_SCREEN.format(sep=SEP), back_menu()
    if view.status == svc.STATUS_LEGACY:
        return INTRO_LEGACY.format(sep=SEP), start_menu()
    extra = (INCOME_LINE.format(amount=format_number(view.pending_income)) if view.pending_income else "") + (
        CD_LINE.format(seconds=view.cooldown) if view.cooldown else ""
    )
    text = SCREEN.format(
        n=view.step + 1, total=len(TRAINING_STEPS), sep=SEP, title=STEP_TITLES[view.code],
        text=STEP_TEXTS[view.code].format(need=TRAINING_POWER_DISTRICTS), map=render_map(view), extra=extra,
    )
    return text, tutorial_menu(view)


async def _show(callback: CallbackQuery, session: AsyncSession, redis: Redis, note: str = "") -> None:
    text, markup = await render(session, redis, callback.from_user.id)
    await safe_edit_text(callback.message, (f"{note}\n\n" if note else "") + text, reply_markup=markup)


async def send_intro(message: Message, session: AsyncSession, redis: Redis, user_id: int) -> None:
    """Новичку сразу после банды — экран первого шага."""
    text, markup = await render(session, redis, user_id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == CB_TUT_OPEN)
async def cb_open(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    await callback.answer()
    await _show(callback, session, redis)


@router.callback_query(F.data == CB_TUT_START)
async def cb_start(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        await svc.start_voluntary(session, callback.from_user.id)
    except svc.TutorialError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer()
    await _show(callback, session, redis)


def _two_ints(raw: str) -> tuple[int, int] | None:
    try:
        a, b = raw.split(":")
        return int(a), int(b)
    except ValueError:
        return None


@router.callback_query(F.data.startswith(CB_TUT_ATTACK_PREFIX))
async def cb_attack(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    target = _two_ints(callback.data.removeprefix(CB_TUT_ATTACK_PREFIX))
    if target is None:
        await callback.answer()
        return
    city, district = target
    try:
        report, adv = await svc.attack(session, redis, callback.from_user.id, city, None if district < 0 else district)
    except svc.TutorialError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    msg = (FIGHT_WON if report.won else FIGHT_LOST).format(
        city=report.city, captured=report.captured, dead=format_number(report.dead), attackers=format_number(report.attackers)
    )
    await callback.answer(msg, show_alert=True)
    await _show(callback, session, redis, advance_text(adv))


@router.callback_query(F.data.startswith(CB_TUT_BUILD_PREFIX))
async def cb_build(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    target = _two_ints(callback.data.removeprefix(CB_TUT_BUILD_PREFIX))
    if target is None:
        await callback.answer()
        return
    try:
        cost, adv = await svc.build(session, callback.from_user.id, *target)
    except svc.TutorialError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(BUILT.format(cost=f" за {format_number(cost)} NHCoin" if cost else " бесплатно"))
    await _show(callback, session, redis, advance_text(adv))


@router.callback_query(F.data == CB_TUT_COLLECT)
async def cb_collect(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        amount, adv = await svc.collect(session, callback.from_user.id)
    except svc.TutorialError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(COLLECTED.format(amount=format_number(amount)) if amount else NOTHING_TO_COLLECT)
    await _show(callback, session, redis, advance_text(adv))


@router.callback_query(F.data == CB_TUT_CHECK)
async def cb_check(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        adv = await svc.acknowledge(session, callback.from_user.id)
    except svc.TutorialError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer("" if adv.done else NOT_YET, show_alert=not adv.done)
    await _show(callback, session, redis, advance_text(adv))
