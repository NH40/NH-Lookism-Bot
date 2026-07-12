"""Еженедельный рейтинг казино."""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.bank.casino.rating_service import casino_rating_service
from app.constants.bank import CASINO_RATING_REWARDS
from app.utils.formatters import fmt_num
from app.utils.safe_edit import safe_edit
from app.utils.keyboards.common import back_kb

router = Router()

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


@router.callback_query(F.data == "bank_casino_rating")
async def cb_casino_rating(cb: CallbackQuery, session: AsyncSession, user: User):
    top = await casino_rating_service.get_top(session, limit=10)

    lines = ["🏆 <b>Рейтинг казино за неделю</b>\n", "<i>Считается только прибыль в NHCoin (слоты, блэкджек, покер)</i>\n"]

    if not top:
        lines.append("Пока никто не выигрывал на этой неделе.")
    else:
        for i, u in enumerate(top, start=1):
            medal = _MEDALS.get(i, f"{i}.")
            name = u.username or u.full_name
            lines.append(f"{medal} {name} — +{fmt_num(u.casino_weekly_coins_won)} NHCoin")

    lines.append("\n<b>Награды топ-3:</b>")
    for rank, reward in CASINO_RATING_REWARDS.items():
        medal = _MEDALS.get(rank, f"{rank}.")
        lines.append(f"{medal} {fmt_num(reward['nh_coins'])} NHCoin + {reward['tickets']} 🎟")
    lines.append("\nРейтинг сбрасывается каждый понедельник в 00:00 UTC.")

    await safe_edit(cb.message, "\n".join(lines), reply_markup=back_kb("bank_casino"))
    await cb.answer()
