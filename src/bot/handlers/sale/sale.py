"""«Пятницы»: экран игрока и раздел админки (хендлеры). Логика — `services/sale`."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.sale import SALE_CHOSEN_MAX
from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, SECTION_SALE
from bot.constant.donate import CB_DONATE_OPEN
from bot.constant.sale import (
    AUDIT_SALE_START,
    AUDIT_SALE_STOP,
    CATEGORIES,
    CB_ADMIN_SALE_START_PREFIX,
    CB_ADMIN_SALE_STOP,
    CB_SALE_BUY_PREFIX,
    CB_SALE_OPEN,
    CB_SALE_PICK_PREFIX,
    SALE_CHOSEN,
    SALE_KINDS,
    SALE_REBIRTH,
    SPECIAL_SALES,
)
from bot.handlers.admin.common import guard
from bot.services import sale as svc
from bot.services.admin import audit
from bot.texts import sale as t
from bot.utils.formatting import format_countdown
from bot.utils.safe_edit import safe_edit_text

log = logging.getLogger(__name__)
router = Router(name="sale")
admin_router = Router(name="admin_sale")
_tasks: set[asyncio.Task] = set()


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _left(until: datetime) -> str:
    return format_countdown(max(0, int((until - datetime.now(timezone.utc)).total_seconds())))


async def banner(session: AsyncSession) -> tuple[str, InlineKeyboardButton | None]:
    """Строка о текущей пятнице для экрана доната и кнопка на её экран."""
    sale = await svc.active(session)
    if sale is None:
        return "", None
    title = t.TITLES[sale.kind]
    return t.BANNER.format(title=title, left=_left(sale.ends_at), about=t.ABOUT[sale.kind]), _btn(t.BTN_SALE.format(title=title), CB_SALE_OPEN)


# --- игрок ---


async def _render(session: AsyncSession, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    v = await svc.view(session, user_id)
    back = [_btn(t.BTN_BACK, CB_DONATE_OPEN)]
    if v.sale is None:
        return t.NONE_ALERT, InlineKeyboardMarkup(inline_keyboard=[back])
    kind = v.sale.kind
    text = t.SCREEN.format(title=t.TITLES[kind], about=t.ABOUT[kind], left=_left(v.sale.ends_at))
    rows = []
    if kind == SALE_CHOSEN:
        text += t.CHOSEN_HINT.format(
            n=len(v.choices), max=SALE_CHOSEN_MAX, list=", ".join(t.CATEGORY_NAMES[c] for c in v.choices) or "—"
        )
        buttons = [
            _btn(t.BTN_PICK.format(mark="✅" if c in v.choices else "▫️", name=t.CATEGORY_NAMES[c]), f"{CB_SALE_PICK_PREFIX}{c}")
            for c in CATEGORIES
        ]
        rows += [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    elif kind in SPECIAL_SALES:
        if v.bought:
            text += t.BOUGHT_LINE
        else:
            rows.append([_btn(t.BTN_BUY.format(price=svc.SPECIAL_PRICES[kind]), f"{CB_SALE_BUY_PREFIX}{kind}")])
    rows.append(back)
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == CB_SALE_OPEN)
async def cb_open(callback: CallbackQuery, session: AsyncSession) -> None:
    text, markup = await _render(session, callback.from_user.id)
    await callback.answer()
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_SALE_PICK_PREFIX))
async def cb_pick(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        await svc.toggle_choice(session, callback.from_user.id, callback.data.removeprefix(CB_SALE_PICK_PREFIX))
    except svc.NoSaleError:
        await callback.answer(t.NONE_ALERT, show_alert=True)
        return
    except svc.TooManyChoicesError:
        await callback.answer(t.TOO_MANY_ALERT, show_alert=True)
        return
    text, markup = await _render(session, callback.from_user.id)
    await callback.answer()
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_SALE_BUY_PREFIX))
async def cb_buy(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        kind = await svc.buy_special(session, redis, callback.from_user.id)
    except svc.SaleBusyError:
        await callback.answer(t.BUSY_ALERT)
        return
    except svc.NoSaleError:
        await callback.answer(t.NONE_ALERT, show_alert=True)
        return
    except svc.AlreadyBoughtError:
        await callback.answer(t.ALREADY_ALERT, show_alert=True)
        return
    except svc.CannotBuyError:
        await callback.answer(t.CANNOT_ALERT, show_alert=True)
        return
    except svc.NotEnoughDonateError as exc:
        await callback.answer(t.NOT_ENOUGH_ALERT.format(price=exc.price, balance=exc.balance), show_alert=True)
        return
    note = t.REBIRTH_DONE if kind == SALE_REBIRTH else ""
    await callback.answer(t.BOUGHT_ALERT.format(title=t.TITLES[kind]) + note, show_alert=True)
    text, markup = await _render(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


# --- админ ---


async def _admin_screen(callback: CallbackQuery, session: AsyncSession) -> None:
    sale = await svc.active(session)
    if sale is not None:
        status = t.ADMIN_ACTIVE.format(title=t.TITLES[sale.kind], left=_left(sale.ends_at))
        rows = [[_btn(t.ADMIN_BTN_STOP, CB_ADMIN_SALE_STOP)]]
    else:
        status = t.ADMIN_NONE
        buttons = [_btn(t.TITLES[k], f"{CB_ADMIN_SALE_START_PREFIX}{k}") for k in SALE_KINDS]
        rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    from bot.constant.admin import CB_ADMIN_OPEN
    from bot.texts.admin.admin import BTN_BACK

    rows.append([_btn(BTN_BACK, CB_ADMIN_OPEN)])
    await safe_edit_text(callback.message, t.ADMIN_SCREEN.format(status=status), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@admin_router.callback_query(F.data == f"{CB_ADMIN_SECTION_PREFIX}{SECTION_SALE}")
async def cb_admin(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_SALE):
        return
    await callback.answer()
    await _admin_screen(callback, session)


@admin_router.callback_query(F.data.startswith(CB_ADMIN_SALE_START_PREFIX))
async def cb_admin_start(callback: CallbackQuery, session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not await guard(callback, session, SECTION_SALE):
        return
    kind = callback.data.removeprefix(CB_ADMIN_SALE_START_PREFIX)
    try:
        sale = await svc.start(session, kind, callback.from_user.id)
    except svc.SaleActiveError:
        await session.rollback()
        await callback.answer(t.ADMIN_ACTIVE_ALERT, show_alert=True)
        return
    except svc.NoSaleError:
        await callback.answer()
        return
    await audit.log(session, callback.from_user.id, AUDIT_SALE_START, None, {"kind": kind, "id": sale.id})
    await session.commit()
    await callback.answer(t.ADMIN_STARTED.format(title=t.TITLES[kind]), show_alert=True)
    task = asyncio.create_task(push_start(callback.bot, session_factory, kind))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    await _admin_screen(callback, session)


@admin_router.callback_query(F.data == CB_ADMIN_SALE_STOP)
async def cb_admin_stop(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_SALE):
        return
    sale = await svc.stop(session)
    if sale is not None:
        await audit.log(session, callback.from_user.id, AUDIT_SALE_STOP, None, {"kind": sale.kind, "id": sale.id})
        await session.commit()
    await callback.answer(t.ADMIN_STOPPED)
    await _admin_screen(callback, session)


async def push_start(bot: Bot, session_factory: async_sessionmaker[AsyncSession], kind: str) -> None:
    """Уведомление всем игрокам о запуске (общая рассылка `services/broadcast`)."""
    try:
        from bot.constant.admin.mass import FLT_ALL
        from bot.services.admin.mass import Audience, Content, run_broadcast

        await run_broadcast(bot, session_factory, Audience(FLT_ALL), Content(t.PUSH_START.format(title=t.TITLES[kind], about=t.ABOUT[kind])))
    except Exception:
        log.exception("Sale %s push failed", kind)
