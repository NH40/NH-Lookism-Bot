import asyncio
import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.formatters import fmt_num
from ._common import _get_slava_top_cached, _phase_emoji

router = Router()


@router.message(Command("slava"))
async def cmd_slava(message: Message, session: AsyncSession, user: User):
    from app.repositories.user_repo import user_repo

    top, my_rank = await asyncio.gather(
        _get_slava_top_cached(session),
        user_repo.get_all_time_rank(session, user.id),
    )

    my_total = (user.all_time_combat_power or 0) + (user.combat_power or 0)

    lines = ["🏛 <b>Зал Славы — общая боевая мощь за всё время</b>\n"]
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}

    for i, u in enumerate(top):
        medal = medals.get(i, f"{i + 1}.")
        vvip = " 👑" if u.ultra_instinct else ""
        prestige = f" ✨{u.prestige_level}" if u.prestige_level else ""
        lines.append(
            f"{medal} <b>{html.escape(u.full_name)}</b>{vvip}{prestige}\n"
            f"   ⚡ {fmt_num(u.total_power)} | {_phase_emoji(u.phase)}"
        )

    lines.append(f"\n📍 Твоё место: #{my_rank}")
    lines.append(f"⚡ Твоя общая мощь: {fmt_num(my_total)}")

    await message.answer("\n".join(lines), parse_mode="HTML")
