"""
Крипто-ферма: 4 монеты с разной волатильностью.
Цена хранится в «микро» (×100) для точных расчётов.
"""
import random
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.bank import CryptoPrice, CryptoHolding
from app.models.user import User

logger = logging.getLogger(__name__)

# ─── Константы монет ──────────────────────────────────────────────────────────
CRYPTO_CONFIG: dict[str, dict] = {
    "CriptoNH": {
        "emoji":       "🟢",
        "name":        "CriptoNH",
        "desc":        "Самая стабильная монета. Растёт медленно, падает редко.",
        "base_price":  100_00,   # 100.00 NHCoin (micro)
        "min_price":   50_00,    # нижний предел
        "max_price":   5_000_00, # верхний предел
        # Умеренный рост: 62% шанс роста, симметричные ±3%
        "tick_up_prob":   62,
        "tick_min_pct":   0,
        "tick_max_pct":   3,
        "tick_drop_pct":  3,
    },
    "CriptoCH": {
        "emoji":       "🔴",
        "name":        "CriptoCH",
        "desc":        "Самая нестабильная монета. Может дать огромный профит или убыток.",
        "base_price":  50_00,
        "min_price":   1_00,
        "max_price":   10_000_00,
        # 55% вверх / 45% вниз компенсирует мультипликативный дрейф вниз —
        # ожидаемый log-доход ≈ 0, цена реально скачет вверх-вниз
        "tick_up_prob":   55,
        "tick_min_pct":   0,
        "tick_max_pct":   30,
        "tick_drop_pct":  25,
    },
    "CriptoVVIP": {
        "emoji":       "🔵",
        "name":        "CriptoVVIP",
        "desc":        "Средняя волатильность. Балансирует между ростом и падением.",
        "base_price":  500_00,
        "min_price":   100_00,
        "max_price":   50_000_00,
        "tick_up_prob":   60,
        "tick_min_pct":   0,
        "tick_max_pct":   20,
        "tick_drop_pct":  15,
    },
    "CriptoWWIP": {
        "emoji":       "🟡",
        "name":        "CriptoWWIP",
        "desc":        "Самая дорогая монета. Колебания небольшие, но ощутимые.",
        "base_price":  5_000_00,
        "min_price":   1_000_00,
        "max_price":   500_000_00,
        "tick_up_prob":   55,
        "tick_min_pct":   0,
        "tick_max_pct":   8,
        "tick_drop_pct":  8,
    },
}

CRYPTO_CURRENCIES = list(CRYPTO_CONFIG.keys())


class CryptoService:

    # ── Инициализация цен ─────────────────────────────────────────────────────

    async def ensure_prices(self, session: AsyncSession) -> None:
        """Создать строки цен для монет, если их нет."""
        for currency, cfg in CRYPTO_CONFIG.items():
            r = await session.execute(
                select(CryptoPrice).where(CryptoPrice.currency == currency)
            )
            if not r.scalar_one_or_none():
                session.add(CryptoPrice(
                    currency=currency,
                    price_micro=cfg["base_price"],
                ))
        await session.flush()

    # ── Получить цены всех монет ──────────────────────────────────────────────

    async def get_all_prices(self, session: AsyncSession) -> dict[str, CryptoPrice]:
        r = await session.execute(select(CryptoPrice))
        rows = r.scalars().all()
        return {row.currency: row for row in rows}

    # ── Тик: обновить цены ────────────────────────────────────────────────────

    async def price_tick(self, session: AsyncSession) -> None:
        """Вызывается из планировщика каждые 5 минут."""
        prices = await self.get_all_prices(session)

        for currency, cfg in CRYPTO_CONFIG.items():
            if currency not in prices:
                # инициализация
                session.add(CryptoPrice(
                    currency=currency, price_micro=cfg["base_price"]
                ))
                continue

            price_row = prices[currency]
            current = price_row.price_micro
            going_up = random.randint(1, 100) <= cfg["tick_up_prob"]

            if going_up:
                pct = random.randint(cfg["tick_min_pct"], cfg["tick_max_pct"])
                new = int(current * (1 + pct / 100))
            else:
                pct = random.randint(0, cfg["tick_drop_pct"])
                new = int(current * (1 - pct / 100))

            # Ограничиваем диапазоном
            new = max(cfg["min_price"], min(cfg["max_price"], new))
            price_row.price_micro = new
            price_row.updated_at = datetime.now(timezone.utc)

        await session.flush()

    # ── Конвертация micro → отображение ──────────────────────────────────────

    @staticmethod
    def micro_to_display(micro: int) -> str:
        """100_00 → '100.00'"""
        return f"{micro // 100}.{micro % 100:02d}"

    @staticmethod
    def price_in_nhcoins(micro: int) -> int:
        """100_50 → 100 NHCoin (округление вниз)."""
        return micro // 100

    # ── Холдинги игрока ───────────────────────────────────────────────────────

    async def get_holding(
        self, session: AsyncSession, user_id: int, currency: str
    ) -> CryptoHolding | None:
        r = await session.execute(
            select(CryptoHolding).where(
                CryptoHolding.user_id == user_id,
                CryptoHolding.currency == currency,
            )
        )
        return r.scalar_one_or_none()

    async def get_all_holdings(
        self, session: AsyncSession, user_id: int
    ) -> dict[str, CryptoHolding]:
        r = await session.execute(
            select(CryptoHolding).where(CryptoHolding.user_id == user_id)
        )
        return {h.currency: h for h in r.scalars().all()}

    # ── Купить крипту ─────────────────────────────────────────────────────────

    async def buy(
        self, session: AsyncSession, user: User, currency: str, units: int
    ) -> tuple[bool, str]:
        if currency not in CRYPTO_CONFIG:
            return False, "❌ Неизвестная валюта."
        if units <= 0:
            return False, "❌ Количество должно быть > 0."

        prices = await self.get_all_prices(session)
        if currency not in prices:
            await self.ensure_prices(session)
            prices = await self.get_all_prices(session)

        price_micro = prices[currency].price_micro
        total_cost = (price_micro * units) // 100  # NHCoin

        if user.nh_coins < total_cost:
            return False, f"❌ Нужно {total_cost:,} NHCoin, у вас {user.nh_coins:,}."

        user.nh_coins -= total_cost

        holding = await self.get_holding(session, user.id, currency)
        if holding:
            # Пересчёт средней цены
            total_spent = holding.avg_buy_price_micro * holding.amount + price_micro * units
            holding.amount += units
            holding.avg_buy_price_micro = total_spent // holding.amount
        else:
            holding = CryptoHolding(
                user_id=user.id,
                currency=currency,
                amount=units,
                avg_buy_price_micro=price_micro,
            )
            session.add(holding)

        await session.flush()
        return True, ""

    # ── Продать крипту ────────────────────────────────────────────────────────

    async def sell(
        self, session: AsyncSession, user: User, currency: str, units: int
    ) -> tuple[bool, str]:
        if currency not in CRYPTO_CONFIG:
            return False, "❌ Неизвестная валюта."

        holding = await self.get_holding(session, user.id, currency)
        if not holding or holding.amount < units:
            return False, f"❌ Недостаточно {currency}."
        if units <= 0:
            return False, "❌ Количество должно быть > 0."

        prices = await self.get_all_prices(session)
        price_micro = prices[currency].price_micro
        revenue = (price_micro * units) // 100

        user.nh_coins += revenue
        holding.amount -= units
        if holding.amount == 0:
            await session.delete(holding)

        await session.flush()
        return True, ""


crypto_service = CryptoService()
