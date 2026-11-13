"""Родословная Пеньгуана (хендлеры). Логика — `services/penguan`."""
from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.penguan import CB_PG_BUFF_PREFIX, CB_PG_BUILDER, CB_PG_BUY_PREFIX, CB_PG_BUYBACK, CB_PG_BUYOUT, CB_PG_OPEN, CB_PG_SET_PREFIX
from bot.db.repositories.user import get_by_id
from bot.keyboards.penguan import builder_menu, main_menu
from bot.services import penguan as svc
from bot.services.build import get_build
from bot.services.country import BattlesClosedError
from bot.texts import penguan as t
from bot.texts.school import SCHOOL_NAMES
from bot.utils.formatting import format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="penguan")


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


async def render(session: AsyncSession, redis: Redis, user_id: int):
    build = await get_build(session, user_id)
    w = await svc.wealth(session, user_id)
    bonuses = ""
    if build.pg.get("pg_attack"):
        from bot.config.penguan import PG_ATTACK_CAP

        bonuses += t.BONUS_ATTACK.format(p=_pct(min(PG_ATTACK_CAP, build.pg["pg_attack"] * w.points)))
    if build.pg.get("pg_influence"):
        from bot.config.penguan import PG_INFLUENCE_CAP

        bonuses += t.BONUS_INFLUENCE.format(p=_pct(min(PG_INFLUENCE_CAP, build.pg["pg_influence"] * w.points)))
    if build.pg.get("pg_land_income"):
        from bot.config.penguan import PG_LAND_INCOME_CAP

        land = build.pg["pg_land_income"] * w.districts / 10 + build.pg.get("pg_city_income", 0.0) * w.cities
        bonuses += t.BONUS_INCOME.format(p=_pct(min(PG_LAND_INCOME_CAP, land)))
    now = datetime.now(timezone.utc)
    offers = await svc.buff_offers(session, user_id)
    buffs = "".join(
        t.BUFF_LINE.format(
            name=t.BUFF_NAMES[o.kind], effect=t.BUFF_EFFECTS[o.kind].format(p=_pct(o.power)), price=format_number(o.price),
            active=t.BUFF_ACTIVE.format(left=format_countdown(int((o.active_until - now).total_seconds()))) if o.active_until else "",
        )
        for o in offers
    )
    extra = ""
    back = await svc.buyback_offer(session, user_id)
    if back is not None:
        extra += t.BUYBACK_LINE.format(units=format_number(back.units), power=format_number(back.power), price=format_number(back.price))
    user = await get_by_id(session, user_id)
    out = await svc.buyout_offer(session, redis, user)
    if out is not None:
        cd = t.BUYOUT_CD.format(left=format_countdown(out.cooldown)) if out.cooldown else ""
        extra += t.BUYOUT_LINE.format(price=format_number(out.price), cd=cd)
    text = t.SCREEN.format(
        income=format_number(w.income), districts=w.districts, cities=w.cities, points=f"{w.points:.2f}",
        bonuses=bonuses, buffs=buffs, extra=extra,
    )
    markup = main_menu(
        offers, builder=bool(build.pg.get("pg_constructor")),
        buyback_price=back.price if back else None, buyout_price=out.price if out and not out.cooldown else None,
    )
    return text, markup


async def _show(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    text, markup = await render(session, redis, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


async def _fail(callback: CallbackQuery, exc: svc.PenguanError) -> None:
    await callback.answer(t.ERRORS[exc.code].format(*(format_number(v) for v in exc.values)), show_alert=exc.code != "busy")


@router.callback_query(F.data == CB_PG_OPEN)
async def cb_open(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    await callback.answer()
    await _show(callback, session, redis)


@router.callback_query(F.data.startswith(CB_PG_BUFF_PREFIX))
async def cb_buff(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        offer = await svc.buy_buff(session, redis, callback.from_user.id, callback.data.removeprefix(CB_PG_BUFF_PREFIX))
    except svc.PenguanError as exc:
        await _fail(callback, exc)
        return
    await callback.answer(t.BUFF_BOUGHT.format(name=t.BUFF_NAMES[offer.kind], price=format_number(offer.price)), show_alert=True)
    await _show(callback, session, redis)


@router.callback_query(F.data == CB_PG_BUYBACK)
async def cb_buyback(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        offer = await svc.buyback(session, redis, callback.from_user.id)
    except svc.PenguanError as exc:
        await _fail(callback, exc)
        return
    await callback.answer(t.BUYBACK_DONE.format(units=format_number(offer.units), price=format_number(offer.price)), show_alert=True)
    await _show(callback, session, redis)


@router.callback_query(F.data == CB_PG_BUYOUT)
async def cb_buyout(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user = await get_by_id(session, callback.from_user.id)
    try:
        number, price, _ = await svc.buyout(session, redis, user)
    except svc.PenguanError as exc:
        await _fail(callback, exc)
        return
    except BattlesClosedError:
        await callback.answer(t.ERRORS["phase"], show_alert=True)
        return
    await callback.answer(t.BUYOUT_DONE.format(number=number, price=format_number(price)), show_alert=True)
    await _show(callback, session, redis)


# --- конструктор ---


async def _show_builder(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    v = await svc.builder_view(session, redis, callback.from_user.id)
    d = v.design
    school = t.SCHOOL_LINE.format(name=SCHOOL_NAMES.get(d.school, d.school), level=d.school_level) if d.school else t.NO_SCHOOL
    text = t.BUILDER.format(
        rank=d.rank, ceiling=v.ceiling, level=d.level, level_cap=v.level_cap, stars=d.stars, school=school,
        power=format_number(int(v.unit_power)), price=format_number(v.unit_price),
        bought=format_number(v.bought_today), cap=format_number(v.daily_cap), left=format_number(v.max_units),
    )
    await safe_edit_text(callback.message, text, reply_markup=builder_menu(v.max_units))


@router.callback_query(F.data == CB_PG_BUILDER)
async def cb_builder(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        await _show_builder(callback, session, redis)
    except svc.PenguanError as exc:
        await _fail(callback, exc)
        return
    await callback.answer()


@router.callback_query(F.data.startswith(CB_PG_SET_PREFIX))
async def cb_set(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    param, _, delta = callback.data.removeprefix(CB_PG_SET_PREFIX).partition(":")
    try:
        if int(delta):
            await svc.change_design(redis, session, callback.from_user.id, param, int(delta))
        await _show_builder(callback, session, redis)
    except svc.PenguanError as exc:
        await _fail(callback, exc)
        return
    except ValueError:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith(CB_PG_BUY_PREFIX))
async def cb_buy(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        n, price = await svc.buy_statists(session, redis, callback.from_user.id, int(callback.data.removeprefix(CB_PG_BUY_PREFIX)))
    except svc.PenguanError as exc:
        await _fail(callback, exc)
        return
    await callback.answer(t.BOUGHT.format(n=format_number(n), price=format_number(price)), show_alert=True)
    await _show_builder(callback, session, redis)
