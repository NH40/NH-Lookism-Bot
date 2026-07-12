import asyncio
import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.formatters import fmt_num
from ._common import _get_fame_alltime_top_cached, _phase_emoji

router = Router()


@router.message(Command("aleya"))
async def cmd_fame_alltime(message: Message, session: AsyncSession, user: User):
    from app.repositories.user_repo import user_repo

    top, my_rank = await asyncio.gather(
        _get_fame_alltime_top_cached(session),
        user_repo.get_fame_alltime_rank(session, user.id),
    )

    lines = ["🛣 <b>Алея Славы — активность за всё время</b>\n"]
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}

    for i, u in enumerate(top):
        medal = medals.get(i, f"{i + 1}.")
        vvip = " 👑" if u.ultra_instinct else ""
        lines.append(
            f"{medal} <b>{html.escape(u.full_name)}</b>{vvip}\n"
            f"   ⭐ {fmt_num(u.fame_alltime_points)} | {_phase_emoji(u.phase)}"
        )

    lines.append(f"\n📍 Твоё место: #{my_rank}")
    lines.append(f"⭐ Твоя активность: {fmt_num(user.fame_alltime_points)}")

    await message.answer("\n".join(lines), parse_mode="HTML")
