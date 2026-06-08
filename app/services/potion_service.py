from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from app.models.potion import ActivePotion
from app.models.user import User


class PotionService:

    # ── Клановые зелья (для всех участников клана) ────────────────────────────
    # Привязаны к тиру 2 новой системы MG_TIERS.
    # Ключи — старые ID для обратной совместимости с кланами.
    CLAN_POTION_CONFIG = {
        "potion_combat":    {"potion_type": "power",     "bonus_value": 40,  "duration_minutes": 30},  # MG Тир 2
        "potion_income":    {"potion_type": "income",    "bonus_value": 40,  "duration_minutes": 60},  # MG Тир 2
        "potion_influence": {"potion_type": "influence", "bonus_value": 40,  "duration_minutes": 45},  # MG Тир 2
        "potion_training":  {"potion_type": "training",  "bonus_value": 35,  "duration_minutes": 60},  # MG Тир 2
        "potion_luck":      {"potion_type": "luck",      "bonus_value": 9,   "duration_minutes": 30},  # MG Тир 2
        "potion_raid_drop": {"potion_type": "raid_drop", "bonus_value": 25,  "duration_minutes": 60},  # MG Тир 2
    }

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
    
    async def activate(
        self, session: AsyncSession, user: User, potion_id: str
    ) -> None:
        """
        Активирует зелье по ID.
        Поддерживает два формата:
          - Старые клановые ID: "potion_combat", "potion_income" и т.д. → CLAN_POTION_CONFIG
          - Новые тировые ID:   "mg_power_2", "mg_income_3" и т.д. → MG_TIER_MAP
        """
        # 1) Проверяем новую тировую систему
        from app.data.shop import MG_TIER_MAP
        mg_cfg = MG_TIER_MAP.get(potion_id)
        if mg_cfg:
            await self.apply_potion(
                session,
                user_id=user.id,
                potion_type=mg_cfg.effect_key,
                bonus_value=mg_cfg.effect_value,
                duration_minutes=mg_cfg.duration_minutes,
            )
            return

        # 2) Старый клановый формат
        cfg = self.CLAN_POTION_CONFIG.get(potion_id)
        if not cfg:
            return
        await self.apply_potion(
            session,
            user_id=user.id,
            potion_type=cfg["potion_type"],
            bonus_value=cfg["bonus_value"],
            duration_minutes=cfg["duration_minutes"],
        )

    async def get_power_bonus(self, session: AsyncSession, user_id: int) -> int:
        """Бонус к боевой мощи от активных зелий (%) — прямой SUM без загрузки всех зелий."""
        now = datetime.now(timezone.utc)
        result = await session.scalar(
            select(func.sum(ActivePotion.bonus_value)).where(
                ActivePotion.user_id == user_id,
                ActivePotion.potion_type == "power",
                ActivePotion.expires_at > now,
            )
        )
        return result or 0

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
        cap = getattr(user, "max_ticket_chance", 70)
        return min(cap, user.ticket_chance + bonus)

    async def get_effective_train_bonus(self, session: AsyncSession, user: User) -> int:
        potions = await self.get_active(session, user.id)
        bonus = sum(p.bonus_value for p in potions if p.potion_type == "training")
        return user.train_bonus_percent + user.prestige_train_bonus + bonus

    async def get_income_bonus(self, session: AsyncSession, user_id: int) -> int:
        potions = await self.get_active(session, user_id)
        return sum(p.bonus_value for p in potions if p.potion_type == "income")

    async def get_raid_drop_bonus(self, session: AsyncSession, user_id: int) -> int:
        now = datetime.now(timezone.utc)
        result = await session.scalar(
            select(func.sum(ActivePotion.bonus_value)).where(
                ActivePotion.user_id == user_id,
                ActivePotion.potion_type == "raid_drop",
                ActivePotion.expires_at > now,
            )
        )
        return result or 0

    _TYPE_LABEL = {
        "power":     "⚔️ Зелье силы",
        "income":    "💰 Зелье богатства",
        "influence": "⚡ Зелье влияния",
        "training":  "🏋 Зелье тренировки",
        "luck":      "🍀 Зелье удачи",
        "raid_drop": "💠 Зелье охотника",
    }

    # Читаемые описания бонуса для уведомлений
    _TYPE_UNIT = {
        "power":     "% мощь",
        "income":    "% доход",
        "influence": "% влияние",
        "training":  "% тренировка",
        "luck":      "% шанс тикета",
        "raid_drop": "% дроп рейда",
    }

    async def buy_missing(self, session: AsyncSession, user: "User") -> None:
        """
        Авто-покупает зелья тира 1 (MG_TIERS), если они не активны и хватает монет.
        Используется Ультра Инстинктом для пользователей без Гения медицины.
        """
        from app.data.shop import MG_TIERS
        active = await self.get_active(session, user.id)
        active_types = {p.potion_type for p in active}
        for ptype, tiers in MG_TIERS.items():
            if ptype in active_types:
                continue
            cfg = tiers[0]  # тир 1
            if user.nh_coins < cfg.price:
                continue
            user.nh_coins -= cfg.price
            user.coins_spent = getattr(user, "coins_spent", 0) + cfg.price
            await self.apply_potion(
                session, user.id,
                cfg.effect_key, cfg.effect_value, cfg.duration_minutes,
            )

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
            label = self._TYPE_LABEL.get(p.potion_type, "🧪 Зелье")
            lines.append(f"  {label}: +{p.bonus_value}% ({time_str})")
        return "\n".join(lines)


potion_service = PotionService()