"""Рейды (хендлеры): пуши и кнопка «встретить лагерем атаки», фоновый проход."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.raid import RAID_DIFFICULTIES, RAID_SWEEP_SECONDS
from bot.constant.settings import NOTIFY_RAID
from bot.services import raid as svc
from bot.services.settings import notify_player
from bot.texts.raid import BTN_FIGHT, CAMP_NAMES, DIFFICULTY_NAMES, NO_RAID, PUSH_LOST, PUSH_WARN, PUSH_WON
from bot.texts.resource import amount_label
from bot.utils.formatting import format_number

log = logging.getLogger(__name__)
router = Router(name="raid")
CB_RAID_FIGHT = "raid:fight"


def outcome_text(o: svc.RaidOutcome) -> str:
    camp = CAMP_NAMES.get(o.camp, o.camp)
    if o.won:
        rewards = ", ".join(amount_label(k, v) for k, v in o.rewards.items())
        return PUSH_WON.format(camp=camp, dead=format_number(o.dead), rewards=rewards)
    return PUSH_LOST.format(camp=camp, dead=format_number(o.dead), lost=o.districts_lost)


@router.callback_query(F.data == CB_RAID_FIGHT)
async def cb_fight(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        outcome = await svc.fight(session, callback.from_user.id)
    except svc.RaidError:
        await callback.answer(NO_RAID, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(outcome_text(outcome))


async def raid_loop(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    menu = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_FIGHT, callback_data=CB_RAID_FIGHT)]])
    while True:
        try:
            for o in await svc.resolve_due(session_factory):
                async with session_factory() as session:
                    await notify_player(bot, session, o.user_id, NOTIFY_RAID, outcome_text(o))
            for r in await svc.spawn(session_factory):
                async with session_factory() as session:
                    text = PUSH_WARN.format(difficulty=DIFFICULTY_NAMES[r.difficulty], power=format_number(r.power), lose=RAID_DIFFICULTIES[r.difficulty][2])
                    await notify_player(bot, session, r.user_id, NOTIFY_RAID, text, reply_markup=menu)
                await asyncio.sleep(0.05)
        except Exception:
            log.exception("Raid sweep failed")
        await asyncio.sleep(RAID_SWEEP_SECONDS)
