from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.potion import ActivePotion
from app.models.user import User


class PotionService:

    async def get_active(self, session: AsyncSession, user_id: int) -> list[ActivePotion]:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(ActivePotion).where(
                ActivePotion.user_id == user_id,
                ActivePotion.expires_at > now,
            )
        )
        return result.scalars().all()

    async def apply_potion(
        self, session: AsyncSession, user_id: int,
        potion_type: str, bonus_value: int, duration_minutes: int
    ) -> ActivePotion:
        """Применяет зелье. Если уже есть — перезаписывает (продлевает)."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=duration_minutes)

        # Удаляем старое того же типа
        await session.execute(
            delete(ActivePotion).where(
                ActivePotion.user_id == user_id,
                ActivePotion.potion_type == potion_type,
            )
        )
        potion = ActivePotion(
            user_id=user_id,
            potion_type=potion_type,
            bonus_value=bonus_value,
            expires_at=expires_at,
        )
        session.add(potion)
        await session.flush()
        return potion

    async def cleanup_expired(self, session: AsyncSession, user_id: int) -> None:
        now = datetime.now(timezone.utc)
        await session.execute(
            delete(ActivePotion).where(
                ActivePotion.user_id == user_id,
                ActivePotion.expires_at <= now,
            )
        )

    # ── Геттеры эффективных значений ────────────────────────────────────────

    async def get_effective_power(self, session: AsyncSession, user: User) -> int:
        potions = await self.get_active(session, user.id)
        bonus = sum(p.bonus_value for p in potions if p.potion_type == "power")
        return int(user.combat_power * (1 + bonus / 100))

    async def get_effective_influence(self, session: AsyncSession, user: User) -> int:
        potions = await self.get_active(session, user.id)
        bonus = sum(p.bonus_value for p in potions if p.potion_type == "influence")
        return int(user.influence * (1 + bonus / 100))

    async def get_effective_ticket_chance(self, session: AsyncSession, user: User) -> int:
        potions = await self.get_active(session, user.id)
        bonus = sum(p.bonus_value for p in potions if p.potion_type == "luck")
        return min(95, user.ticket_chance + bonus)

    async def get_effective_train_bonus(self, session: AsyncSession, user: User) -> int:
        potions = await self.get_active(session, user.id)
        bonus = sum(p.bonus_value for p in potions if p.potion_type == "training")
        return user.train_bonus_percent + user.prestige_train_bonus + bonus

    async def get_income_bonus(self, session: AsyncSession, user_id: int) -> int:
        potions = await self.get_active(session, user_id)
        return sum(p.bonus_value for p in potions if p.potion_type == "income")

    async def get_active_summary(self, session: AsyncSession, user_id: int) -> str:
        """Текстовое описание активных зелий для UI."""
        now = datetime.now(timezone.utc)
        potions = await self.get_active(session, user_id)
        if not potions:
            return ""
        lines = []
        for p in potions:
            remaining = int((p.expires_at - now).total_seconds())
            m, s = divmod(remaining, 60)
            time_str = f"{m}м {s}с" if m else f"{s}с"
            lines.append(f"  🧪 +{p.bonus_value}% ({time_str})")
        return "\n".join(lines)


potion_service = PotionService()