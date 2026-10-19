"""Админка: действия над игроком из карточки (сервис) — выдача/изъятие, развитие, наказания.

Все функции записи — шаги одной админской операции и НЕ коммитят: коммит (вместе с записью в
журнал аудита) делает хендлер ровно один раз.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.game import NH_COINS_STARTING, TICKET_STARTING
from bot.constant.admin.players_admin import (
    COOLDOWN_KEY_PATTERNS,
    DEV_KIND_GENIUS,
    DEV_KIND_PATH,
    DEV_KIND_TECH,
)
from bot.constant.characteristic import RANK_LADDER
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
from bot.db.models.clan import Clan, ClanMember
from bot.db.models.development import UserGenius, UserPath, UserTechnique
from bot.db.models.user import User
from bot.db.repositories.battle_pass import battle_pass as bp_repo
from bot.db.repositories.card.card import add_to_stack as add_card_to_stack
from bot.db.repositories.card.card import get_stack_for_update as get_card_stack
from bot.db.repositories.gang.reset import reset_player
from bot.services.battle_pass.battle_pass import current_season
from bot.services import resource
from bot.services.bloodline import apply_effects as apply_bloodline_effects
from bot.services.donate import apply_all as apply_donate
from bot.services.resource.statists import StatistKey, give_statists, take_statists

# Система развития → (модель владения, колонка активного).
_DEV_SYSTEMS = {
    DEV_KIND_PATH: (UserPath, User.active_path),
    DEV_KIND_TECH: (UserTechnique, User.active_technique),
    DEV_KIND_GENIUS: (UserGenius, User.active_genius),
}


class NotEnoughError(Exception):
    def __init__(self, have: int = 0) -> None:
        self.have = have


class OwnerBlockedError(Exception):
    def __init__(self, members: int) -> None:
        self.members = members


# ----------------------------- выдача / изъятие -----------------------------

async def give_resource(session: AsyncSession, user_id: int, code: str, delta: int) -> tuple[int, int]:
    """Начислить (delta>0) или забрать (delta<0, не ниже нуля). → (фактическое изменение, баланс)."""
    balance = await resource.balance(session, user_id, code)
    if delta > 0:
        await resource.grant(session, user_id, code, delta)
        applied = delta
    else:
        applied = -min(-delta, balance)
        if applied and not await resource.spend(session, user_id, code, -applied):
            raise NotEnoughError(balance)
    return applied, balance + applied


async def give_statist(session: AsyncSession, user_id: int, key: StatistKey, delta: int) -> None:
    if delta > 0:
        await give_statists(session, user_id, key, delta)
    elif not await take_statists(session, user_id, key, -delta):
        raise NotEnoughError


async def give_card(session: AsyncSession, user_id: int, card_code: str, delta: int) -> None:
    if delta > 0:
        await add_card_to_stack(session, user_id=user_id, card_code=card_code, camp=CAMP_DEFENSE, quantity=delta)
        return
    stacks = []
    for camp in (CAMP_DEFENSE, CAMP_ATTACK):
        stack = await get_card_stack(session, user_id=user_id, card_code=card_code, camp=camp)
        stacks.append((camp, stack.quantity if stack else 0))
    total = sum(q for _, q in stacks)
    if total < -delta:
        raise NotEnoughError(total)
    left = -delta
    for camp, have in stacks:
        take = min(have, left)
        if take:
            await add_card_to_stack(session, user_id=user_id, card_code=card_code, camp=camp, quantity=-take)
            left -= take


async def skip_scrolls(session: AsyncSession, user_id: int) -> int:
    return int(await session.scalar(select(User.skip_scrolls).where(User.id == user_id)) or 0)


async def add_skip_scrolls(session: AsyncSession, user_id: int, delta: int) -> int:
    return int(await session.scalar(
        update(User).where(User.id == user_id).values(skip_scrolls=func.greatest(User.skip_scrolls + delta, 0))
        .returning(User.skip_scrolls)
    ) or 0)


async def bp_xp(session: AsyncSession, user_id: int) -> int:
    season = await current_season(session)
    row = await bp_repo.get(session, user_id, season.id)
    return row.xp if row else 0


async def add_bp_xp(session: AsyncSession, user_id: int, delta: int) -> int:
    """Опыт напрямую в строку пасса (без дневного буста, в отличие от `add_xp`)."""
    season = await current_season(session)
    row = await bp_repo.lock(session, user_id, season.id)
    row.xp = max(0, row.xp + delta)
    await session.flush()
    return row.xp


# --------------------------------- развитие ---------------------------------

async def dev_state(session: AsyncSession, user_id: int, kind: str) -> tuple[dict[str, int], str | None]:
    """(код → уровень у игрока, активный код)."""
    model, active_col = _DEV_SYSTEMS[kind]
    rows = await session.execute(select(model.code, model.level).where(model.user_id == user_id))
    active = await session.scalar(select(active_col).where(User.id == user_id))
    return {code: level for code, level in rows.all()}, active


async def set_dev_level(session: AsyncSession, user_id: int, kind: str, code: str, level: int) -> None:
    """Выдать/выставить уровень; 0 — забрать (с активного — снять активность)."""
    model, active_col = _DEV_SYSTEMS[kind]
    if level <= 0:
        await session.execute(delete(model).where(model.user_id == user_id, model.code == code))
        await session.execute(update(User).where(User.id == user_id, active_col == code).values({active_col.key: None}))
        return
    await session.execute(
        pg_insert(model).values(user_id=user_id, code=code, level=level)
        .on_conflict_do_update(index_elements=[model.user_id, model.code], set_={"level": level})
    )
    await session.execute(  # первый выданный — сразу активный, как при обычном получении
        update(User).where(User.id == user_id, active_col.is_(None)).values({active_col.key: code})
    )


async def set_dev_active(session: AsyncSession, user_id: int, kind: str, code: str) -> bool:
    model, active_col = _DEV_SYSTEMS[kind]
    if await session.scalar(select(model.code).where(model.user_id == user_id, model.code == code)) is None:
        return False
    await session.execute(update(User).where(User.id == user_id).values({active_col.key: code}))
    return True


async def bloodline_state(session: AsyncSession, user_id: int, slot: int) -> tuple[str | None, int]:
    if slot == 2:
        row = (await session.execute(select(User.bloodline2, User.bloodline2_level).where(User.id == user_id))).one()
    else:
        row = (await session.execute(select(User.bloodline, User.bloodline_level).where(User.id == user_id))).one()
    return row[0], row[1]


async def set_bloodline(session: AsyncSession, user_id: int, slot: int, code: str | None, level: int) -> None:
    values = {"bloodline2": code, "bloodline2_level": level} if slot == 2 else {"bloodline": code, "bloodline_level": level}
    await session.execute(update(User).where(User.id == user_id).values(**values))
    await apply_bloodline_effects(session, user_id)


async def toggle_second_body(session: AsyncSession, user_id: int) -> bool:
    return bool(await session.scalar(
        update(User).where(User.id == user_id).values(second_body=~User.second_body).returning(User.second_body)
    ))


async def premium_pass(session: AsyncSession, user_id: int) -> bool:
    season = await current_season(session)
    row = await bp_repo.get(session, user_id, season.id)
    return bool(row and row.is_premium)


async def toggle_premium_pass(session: AsyncSession, user_id: int) -> bool:
    season = await current_season(session)
    row = await bp_repo.lock(session, user_id, season.id)
    row.is_premium = not row.is_premium
    await session.flush()
    return row.is_premium


async def set_awakening(session: AsyncSession, user_id: int, level: int) -> None:
    await session.execute(update(User).where(User.id == user_id).values(awakening_level=level))


async def set_potential(session: AsyncSession, user_id: int, potential: str) -> None:
    await session.execute(update(User).where(User.id == user_id).values(potential=potential))


async def stat_ranks(session: AsyncSession, user_id: int) -> dict[str, int]:
    row = (await session.execute(
        select(User.stat_strength, User.stat_speed, User.stat_endurance, User.stat_agility).where(User.id == user_id)
    )).one()
    return dict(zip(("strength", "speed", "endurance", "agility"), row))


def parse_rank(raw: str) -> int | None:
    """Индекс ранга в лестнице по имени (без учёта регистра)."""
    wanted = raw.strip().upper()
    for i, rank in enumerate(RANK_LADDER):
        if rank.upper() == wanted:
            return i
    return None


async def set_stat_rank(session: AsyncSession, user_id: int, stat: str, rank_index: int) -> None:
    await session.execute(update(User).where(User.id == user_id).values({f"stat_{stat}": rank_index}))


# -------------------------------- наказания ---------------------------------

async def ban(session: AsyncSession, user_id: int, seconds: int | None, reason: str | None) -> datetime | None:
    """Бан: `seconds=None` — бессрочный. → дата окончания (None — навсегда)."""
    until = None if seconds is None else datetime.now(timezone.utc) + timedelta(seconds=seconds)
    await session.execute(
        update(User).where(User.id == user_id).values(is_banned=until is None, banned_until=until, ban_reason=reason)
    )
    return until


async def unban(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(is_banned=False, banned_until=None, ban_reason=None)
    )


async def clear_cooldowns(redis: Redis, user_id: int) -> int:
    """Удалить кулдауны и щиты игрока в Redis. → число удалённых ключей."""
    removed = 0
    for pattern in COOLDOWN_KEY_PATTERNS:
        keys = [key async for key in redis.scan_iter(match=pattern.format(uid=user_id), count=200)]
        if keys:
            removed += await redis.delete(*keys)
    return removed


async def reset_progress(session: AsyncSession, user_id: int) -> None:
    """Полный сброс прогресса — тот же путь, что удаление банды игроком, без подтверждения в Redis."""
    await reset_player(session, user_id, nh_coins=NH_COINS_STARTING, tickets=TICKET_STARTING)
    await apply_bloodline_effects(session, user_id)
    await apply_donate(session, user_id)


async def delete_account(session: AsyncSession, user_id: int) -> None:
    """Удалить игрока совсем. Владелец клана с участниками — `OwnerBlockedError`; клан без
    других участников удаляется вместе с ним. Незакрытые связи — `IntegrityError` (откатывает хендлер)."""
    clan_id = await session.scalar(select(Clan.id).where(Clan.owner_id == user_id))
    if clan_id is not None:
        members = int(await session.scalar(select(func.count()).select_from(ClanMember).where(ClanMember.clan_id == clan_id)) or 0)
        if members > 1:
            raise OwnerBlockedError(members - 1)
        await session.execute(delete(Clan).where(Clan.id == clan_id))
    await reset_player(session, user_id, nh_coins=0, tickets=0)  # освобождает районы, вызовы, ячейки
    await session.execute(text("DELETE FROM district_challenges WHERE attacker_id = :u OR defender_id = :u"), {"u": user_id})
    await session.execute(delete(User).where(User.id == user_id))



async def wipe_statists(session: AsyncSession, user_id: int) -> int:
    """Забрать у игрока всех статистов (обе стопки лагерей). → сколько было. НЕ коммитит."""
    from sqlalchemy import func, select, text

    from bot.db.models.extra import Extra

    total = int(await session.scalar(select(func.coalesce(func.sum(Extra.quantity), 0)).where(Extra.user_id == user_id)) or 0)
    await session.execute(text("DELETE FROM extras WHERE user_id = :u"), {"u": user_id})
    return total


class EmperorTakenError(Exception):
    pass


async def set_phase(session: AsyncSession, user_id: int, phase: str) -> None:
    """Перевести игрока в фазу (быстрые тесты, 2026-10-13). Кулак — коронация как в игре (города
    страны, районы → владения), один император на страну; из кулака — города и персональные
    налоги снимаются, владения остаются. Банда ↔ круг — просто фаза. НЕ коммитит."""
    from sqlalchemy import delete, update

    from bot.constant.phase import PHASE_FIST, PHASE_ORDER
    from bot.db.models.city import City
    from bot.db.models.emperor_tax import EmperorTaxOverride
    from bot.db.models.user import User
    from bot.db.repositories import phase as phase_repo

    if phase not in PHASE_ORDER:
        raise ValueError(phase)
    current, country = await phase_repo.get_phase(session, user_id)
    if phase == current:
        return
    if phase == PHASE_FIST:
        other = await phase_repo.country_emperor(session, country, exclude_user_id=user_id)
        if other is not None:
            raise EmperorTakenError
        from bot.services.phase import crown_with_autobuild

        await crown_with_autobuild(session, user_id, country)
        return
    if current == PHASE_FIST:
        await session.execute(update(City).where(City.emperor_id == user_id).values(emperor_id=None))
        await session.execute(delete(EmperorTaxOverride).where(EmperorTaxOverride.emperor_id == user_id))
    await session.execute(update(User).where(User.id == user_id).values(phase=phase))
