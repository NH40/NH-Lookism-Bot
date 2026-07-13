import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fame import FameFragment
from app.models.user import User
from app.data.fame import FAME_SETS, FAME_SET_MAP, FAME_FORGE_COST, fame_fragment_key, get_fragment_def
from app.services.cooldown_service import cooldown_service

logger = logging.getLogger(__name__)

ELITE_HOLDER_KEY = "fame:elite_holder_id"
_OVERCOME_KEY_FMT = "fame:overcome:{user_id}"
OVERCOME_MAX_STACKS = 5
OVERCOME_STACK_SECONDS = 20 * 60
OVERCOME_PCT_PER_STACK = 5


class FameService:

    # ── Кузница: сид, выковка, передача, админ-выдача ─────────────────────────

    async def seed_fragments(self, session: AsyncSession) -> None:
        """Идемпотентно создаёт недостающие строки фрагментов для реальных сетов.

        Вызывается при старте бота (см. app/main.py), как init_cities().
        """
        existing = set((await session.execute(select(FameFragment.fragment_key))).scalars().all())
        added = False
        for s in FAME_SETS:
            if s.stub:
                continue
            for f in s.fragments:
                key = fame_fragment_key(s.set_key, f.key)
                if key not in existing:
                    session.add(FameFragment(fragment_key=key))
                    added = True
        if added:
            await session.flush()

    async def has_available_fragment(self, session: AsyncSession) -> bool:
        r = await session.scalar(
            select(FameFragment.id).where(FameFragment.owner_user_id.is_(None)).limit(1)
        )
        return r is not None

    async def get_owned_fragments(self, session: AsyncSession, user_id: int) -> set[str]:
        rows = (await session.execute(
            select(FameFragment.fragment_key).where(FameFragment.owner_user_id == user_id)
        )).scalars().all()
        return set(rows)

    async def get_set_fragments(self, session: AsyncSession, set_key: str) -> list[FameFragment]:
        s = FAME_SET_MAP.get(set_key)
        if not s:
            return []
        keys = [fame_fragment_key(set_key, f.key) for f in s.fragments]
        if not keys:
            return []
        return list((await session.execute(
            select(FameFragment).where(FameFragment.fragment_key.in_(keys))
        )).scalars().all())

    async def forge_fragment(self, session: AsyncSession, user: User, set_key: str, frag_key: str) -> dict:
        s = FAME_SET_MAP.get(set_key)
        if not s or s.stub:
            return {"ok": False, "reason": "Сет пока недоступен"}
        fdef = get_fragment_def(set_key, frag_key)
        if not fdef:
            return {"ok": False, "reason": "Фрагмент не найден"}

        key = fame_fragment_key(set_key, frag_key)
        frag = await session.scalar(select(FameFragment).where(FameFragment.fragment_key == key))
        if not frag:
            return {"ok": False, "reason": "Фрагмент не найден"}
        if frag.owner_user_id is not None:
            return {"ok": False, "reason": "Этот фрагмент уже выкован другим игроком"}

        if (user.fame_alltime_points or 0) < FAME_FORGE_COST:
            return {"ok": False, "reason": f"Недостаточно очков активности Алеи славы (нужно {FAME_FORGE_COST})"}

        user.fame_alltime_points -= FAME_FORGE_COST
        frag.owner_user_id = user.id
        frag.forged_at = datetime.now(timezone.utc)
        await session.flush()

        await self.recalc_fame_bonuses(session, user)
        await self._refresh_elite_cache(session)

        return {"ok": True, "set_name": s.name, "name": fdef.name}

    async def transfer_fragment(
        self, session: AsyncSession, from_user: User, to_user: User, set_key: str, frag_key: str
    ) -> dict:
        if from_user.id == to_user.id:
            return {"ok": False, "reason": "Нельзя передать самому себе"}
        fdef = get_fragment_def(set_key, frag_key)
        if not fdef:
            return {"ok": False, "reason": "Фрагмент не найден"}
        key = fame_fragment_key(set_key, frag_key)
        frag = await session.scalar(select(FameFragment).where(FameFragment.fragment_key == key))
        if not frag or frag.owner_user_id != from_user.id:
            return {"ok": False, "reason": "У тебя нет этого фрагмента"}

        frag.owner_user_id = to_user.id
        await session.flush()

        await self.recalc_fame_bonuses(session, from_user)
        await self.recalc_fame_bonuses(session, to_user)
        await self._refresh_elite_cache(session)

        return {"ok": True, "name": fdef.name}

    async def transfer_full_set(self, session: AsyncSession, from_user: User, to_user: User, set_key: str) -> dict:
        if from_user.id == to_user.id:
            return {"ok": False, "reason": "Нельзя передать самому себе"}
        s = FAME_SET_MAP.get(set_key)
        if not s or s.stub:
            return {"ok": False, "reason": "Сет не найден"}

        frags = await self.get_set_fragments(session, set_key)
        if len(frags) != len(s.fragments) or any(f.owner_user_id != from_user.id for f in frags):
            return {"ok": False, "reason": "У тебя нет всех частей этого сета"}

        for f in frags:
            f.owner_user_id = to_user.id
        await session.flush()

        await self.recalc_fame_bonuses(session, from_user)
        await self.recalc_fame_bonuses(session, to_user)
        await self._refresh_elite_cache(session)

        return {"ok": True, "set_name": s.name}

    async def admin_grant_fragment(self, session: AsyncSession, user: User, set_key: str, frag_key: str) -> dict:
        """Выдаёт фрагмент напрямую (админ-панель). Если фрагмент уже у кого-то — забирает у него."""
        s = FAME_SET_MAP.get(set_key)
        if not s or s.stub:
            return {"ok": False, "reason": "Сет пока недоступен"}
        fdef = get_fragment_def(set_key, frag_key)
        if not fdef:
            return {"ok": False, "reason": "Фрагмент не найден"}
        key = fame_fragment_key(set_key, frag_key)
        frag = await session.scalar(select(FameFragment).where(FameFragment.fragment_key == key))
        if not frag:
            return {"ok": False, "reason": "Фрагмент не найден"}

        prev_owner_id = frag.owner_user_id
        frag.owner_user_id = user.id
        frag.forged_at = datetime.now(timezone.utc)
        await session.flush()

        if prev_owner_id and prev_owner_id != user.id:
            prev_owner = await session.get(User, prev_owner_id)
            if prev_owner:
                await self.recalc_fame_bonuses(session, prev_owner)

        await self.recalc_fame_bonuses(session, user)
        await self._refresh_elite_cache(session)

        return {"ok": True, "set_name": s.name, "name": fdef.name}

    async def admin_grant_full_set(self, session: AsyncSession, user: User, set_key: str) -> dict:
        s = FAME_SET_MAP.get(set_key)
        if not s or s.stub:
            return {"ok": False, "reason": "Сет пока недоступен"}
        for f in s.fragments:
            await self.admin_grant_fragment(session, user, set_key, f.key)
        return {"ok": True, "set_name": s.name}

    async def recalc_fame_bonuses(self, session: AsyncSession, user: User) -> None:
        """Пересчитывает кэшированные fame_* поля user из владения фрагментами."""
        owned = await self.get_owned_fragments(session, user.id)

        user.fame_gaprena_leader = fame_fragment_key("gaprena", "leader") in owned
        user.fame_gaprena_hero = fame_fragment_key("gaprena", "hero") in owned
        user.fame_gaprena_romantic = fame_fragment_key("gaprena", "romantic") in owned
        user.fame_set_gaprena = (
            user.fame_gaprena_leader and user.fame_gaprena_hero and user.fame_gaprena_romantic
        )

        user.fame_gana_ui_control = fame_fragment_key("gana", "ui_control") in owned
        user.fame_gana_monster = fame_fragment_key("gana", "monster") in owned
        user.fame_gana_path = fame_fragment_key("gana", "path_building") in owned
        user.fame_set_gana = user.fame_gana_ui_control and user.fame_gana_monster and user.fame_gana_path

        user.fame_charles_geniuses = fame_fragment_key("charles_choi", "ten_geniuses") in owned
        user.fame_charles_nhn_group = fame_fragment_key("charles_choi", "nhn_group") in owned
        user.fame_charles_invisible = fame_fragment_key("charles_choi", "invisible_attacks") in owned
        user.fame_set_charles = (
            user.fame_charles_geniuses and user.fame_charles_nhn_group and user.fame_charles_invisible
        )

        await session.flush()

    async def _refresh_elite_cache(self, session: AsyncSession) -> None:
        """Redis-кэш владельца сета Элиты — читается при расчёте цен по всей игре."""
        holder_id = await session.scalar(select(User.id).where(User.fame_set_charles == True).limit(1))
        try:
            if holder_id:
                await cooldown_service.redis.set(ELITE_HOLDER_KEY, str(holder_id))
            else:
                await cooldown_service.redis.delete(ELITE_HOLDER_KEY)
        except Exception:
            logger.warning("fame_service: failed to refresh elite cache", exc_info=True)

    async def get_price_multiplier(self, user: User) -> float:
        """+20% ко всем ценам для всех, КРОМЕ владельца полного сета Чарльз Чоя (бафф «Элита»)."""
        try:
            holder_id = await cooldown_service.redis.get(ELITE_HOLDER_KEY)
        except Exception:
            return 1.0
        if not holder_id or int(holder_id) == user.id:
            return 1.0
        return 1.2

    async def get_craft_cost_multiplier(self, user: User) -> float:
        """Множитель на стоимость крафтов в рейдах: титул «Игрок» -15%, + бафф «Элита» +20% (кроме владельца)."""
        mult = await self.get_price_multiplier(user)
        if getattr(user, "title_casino_player", False):
            mult *= 0.85
        return mult

    # ── Бафф «Преодоление» (сет Гапрена) — стак за атаку, 20 мин, до 5 стаков ─

    async def gain_overcome_stack(self, user_id: int) -> None:
        key = _OVERCOME_KEY_FMT.format(user_id=user_id)
        try:
            current = await cooldown_service.redis.get(key)
            stacks = min(OVERCOME_MAX_STACKS, (int(current) if current else 0) + 1)
            await cooldown_service.redis.setex(key, OVERCOME_STACK_SECONDS, str(stacks))
        except Exception:
            logger.warning("fame_service: failed to update overcome stack", exc_info=True)

    async def get_overcome_bonus_pct(self, user_id: int) -> int:
        key = _OVERCOME_KEY_FMT.format(user_id=user_id)
        try:
            current = await cooldown_service.redis.get(key)
        except Exception:
            return 0
        if not current:
            return 0
        return int(current) * OVERCOME_PCT_PER_STACK


fame_service = FameService()
