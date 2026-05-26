from datetime import datetime, timezone
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.boss import ActiveBoss
from app.models.boss_attack import BossAttack


class BossRepo:

    # ── ActiveBoss ────────────────────────────────────────────────────────────

    async def get_current_boss(self, session: AsyncSession) -> ActiveBoss | None:
        """Возвращает активного босса (status=active и expires_at ещё не прошло)."""
        now = datetime.now(timezone.utc)
        return await session.scalar(
            select(ActiveBoss).where(
                ActiveBoss.status == "active",
                ActiveBoss.expires_at > now,
            )
        )

    async def get_current_boss_for_update(self, session: AsyncSession) -> ActiveBoss | None:
        """Активный босс с блокировкой строки (SELECT FOR UPDATE)."""
        now = datetime.now(timezone.utc)
        return await session.scalar(
            select(ActiveBoss).where(
                ActiveBoss.status == "active",
                ActiveBoss.expires_at > now,
            ).with_for_update()
        )

    async def get_expired_active(self, session: AsyncSession) -> ActiveBoss | None:
        """Активный босс, у которого истёк expires_at."""
        now = datetime.now(timezone.utc)
        return await session.scalar(
            select(ActiveBoss).where(
                ActiveBoss.status == "active",
                ActiveBoss.expires_at <= now,
            )
        )

    async def get_last_boss(self, session: AsyncSession) -> ActiveBoss | None:
        """Последний завершённый/истёкший босс."""
        return await session.scalar(
            select(ActiveBoss)
            .where(ActiveBoss.status != "active")
            .order_by(desc(ActiveBoss.id))
            .limit(1)
        )

    async def get_pending_spawn(self, session: AsyncSession) -> ActiveBoss | None:
        """Последний завершённый босс, у которого next_spawn_at уже наступил."""
        now = datetime.now(timezone.utc)
        return await session.scalar(
            select(ActiveBoss)
            .where(
                ActiveBoss.status != "active",
                ActiveBoss.next_spawn_at != None,
                ActiveBoss.next_spawn_at <= now,
            )
            .order_by(desc(ActiveBoss.id))
            .limit(1)
        )

    async def create_boss(
        self,
        session: AsyncSession,
        boss_id: str,
        hp: int,
        started_at: datetime,
        expires_at: datetime,
        state: dict,
    ) -> ActiveBoss:
        boss = ActiveBoss(
            boss_id=boss_id,
            hp=hp,
            base_max_hp=hp,
            current_max_hp=hp,
            status="active",
            started_at=started_at,
            expires_at=expires_at,
        )
        boss.set_state(state)
        session.add(boss)
        await session.flush()
        return boss

    async def finish_boss(
        self,
        session: AsyncSession,
        boss: ActiveBoss,
        defeated: bool,
        next_spawn_at: datetime,
    ) -> None:
        boss.status = "defeated" if defeated else "expired"
        boss.defeated = defeated
        boss.next_spawn_at = next_spawn_at
        await session.flush()

    # ── BossAttack ────────────────────────────────────────────────────────────

    async def get_attack_record(
        self, session: AsyncSession, boss_record_id: int, user_id: int
    ) -> BossAttack | None:
        return await session.scalar(
            select(BossAttack).where(
                BossAttack.boss_record_id == boss_record_id,
                BossAttack.user_id == user_id,
            )
        )

    async def get_or_create_attack(
        self, session: AsyncSession, boss_record_id: int, user_id: int
    ) -> BossAttack:
        rec = await self.get_attack_record(session, boss_record_id, user_id)
        if rec:
            return rec
        rec = BossAttack(boss_record_id=boss_record_id, user_id=user_id)
        session.add(rec)
        await session.flush()
        return rec

    async def get_top_attackers(
        self, session: AsyncSession, boss_record_id: int, limit: int = 10
    ) -> list[BossAttack]:
        result = await session.execute(
            select(BossAttack)
            .where(BossAttack.boss_record_id == boss_record_id)
            .order_by(desc(BossAttack.damage_dealt))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_all_attackers(
        self, session: AsyncSession, boss_record_id: int
    ) -> list[BossAttack]:
        result = await session.execute(
            select(BossAttack).where(BossAttack.boss_record_id == boss_record_id)
        )
        return list(result.scalars().all())


boss_repo = BossRepo()
