"""Абсолютные карты после боя (сервис): Ариан (блок абсолютов цели на час), Менеджер (у
напавшего сгорает доля NHCoin), Marise (клон доли выживших статистов после атаки). НЕ
коммитит — коммитит вызывающий бой сервис (правило 10). Возвращает строки для журнала боя."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.absolute import ARIAN_BLOCK_SECONDS, MANAGER_COINS_BURN, MARISE_CLONE, MARISE_CLONE_CAP
from bot.constant.absolute import ABS_MANAGER, ABS_MARISE
from bot.constant.extra import CAMP_ATTACK
from bot.db.models.user import User
from bot.db.repositories.extra import add_to_stack
from bot.services.absolute.absolute import active
from bot.texts.absolute import JOURNAL_ARIAN, JOURNAL_MANAGER, JOURNAL_MARISE
from bot.utils.formatting import format_number

_KIND_EXTRA = "x"  # ключ стопки статистов в бою (`services/district/army`)


async def after_battle(session: AsyncSession, m, result, *, attacker_id: int, attacker_stacks=None,
                       defender_id: int | None = None) -> tuple[str, ...]:
    lines: list[str] = []
    attacker_abs = await active(session, attacker_id)
    defender_abs = frozenset() if defender_id is None or m.arian else await active(session, defender_id)
    if m.arian and defender_id is not None:
        until = datetime.now(timezone.utc) + timedelta(seconds=ARIAN_BLOCK_SECONDS)
        await session.execute(update(User).where(User.id == defender_id).values(absolute_blocked_until=until))
        lines.append(JOURNAL_ARIAN)
    if ABS_MANAGER in defender_abs:
        coins = await session.scalar(select(User.nh_coins).where(User.id == attacker_id).with_for_update()) or 0
        burned = int(coins * MANAGER_COINS_BURN)
        if burned:
            await session.execute(update(User).where(User.id == attacker_id).values(nh_coins=User.nh_coins - burned))
        lines.append(JOURNAL_MANAGER.format(amount=format_number(burned)))
    if ABS_MARISE in attacker_abs and attacker_stacks:
        dead = result.attacker.dead
        budget = MARISE_CLONE_CAP
        cloned = 0
        for s in attacker_stacks:
            if budget <= 0 or not (isinstance(s.key, tuple) and s.key and s.key[0] == _KIND_EXTRA):
                continue
            alive = s.quantity - dead.get(s.key, 0)
            extra = min(budget, int(alive * MARISE_CLONE))
            if extra <= 0:
                continue
            _, rank, stars, level, school, school_level = s.key
            await add_to_stack(session, user_id=attacker_id, camp=CAMP_ATTACK, rank=rank, stars=stars, training_level=level,
                               quantity=extra, school=school, school_level=school_level)
            budget -= extra
            cloned += extra
        if cloned:
            lines.append(JOURNAL_MARISE.format(count=format_number(cloned)))
    return tuple(lines)
