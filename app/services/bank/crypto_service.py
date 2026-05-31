"""
Крипто-ферма: 4 монеты с живым рынком (маркет-мейкер).
Цена хранится в «микро» (×100) для точных расчётов.
Каждая сделка двигает цену по формуле убывающего влияния.
"""
import random
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.bank import CryptoPrice, CryptoHolding
from app.models.user import User

logger = logging.getLogger(__name__)

# Комиссия биржи при продаже крипты (% от выручки, целое число)
SELL_COMMISSION_PCT = 5

# ─── Конфиг монет ─────────────────────────────────────────────────────────────
# liquidity        — виртуальная глубина рынка (NHCoin); чем выше — тем меньше
#                    одна сделка двигает цену
# max_trade_impact — потолок влияния одной сделки на цену (%)
# reversion_speed  — скорость возврата к базовой цене за тик (доля отклонения)
# maker_strength   — сила маркет-мейкера (0..1); насколько агрессивно бот
#                    противодействует дисбалансу спроса/предложения
# noise_pct        — случайный шум ±% за тик (имитирует естественные колебания)
CRYPTO_CONFIG: dict[str, dict] = {
    "CriptoNH": {
        "emoji":            "🟢",
        "name":             "CriptoNH",
        "desc":             "Самая стабильная монета. Медленно реагирует на рынок.",
        "base_price":       100_00,
        "min_price":        50_00,
        "max_price":        5_000_00,
        "liquidity":        200_000,    # NHCoin
        "max_trade_impact": 5.0,        # %
        "reversion_speed":  0.025,
        "maker_strength":   0.6,
        "noise_pct":        1.0,
    },
    "CriptoCH": {
        "emoji":            "🔴",
        "name":             "CriptoCH",
        "desc":             "Самая нестабильная монета. Сильно реагирует на каждую сделку.",
        "base_price":       50_00,
        "min_price":        1_00,
        "max_price":        10_000_00,
        "liquidity":        150_000,    # NHCoin (увеличено ×5 — сложнее манипулировать)
        "max_trade_impact": 10.0,       # снижено с 20% → сложнее памп-дамп
        "reversion_speed":  0.030,      # быстрее возврат к базе
        "maker_strength":   0.5,
        "noise_pct":        5.0,
    },
    "CriptoVVIP": {
        "emoji":            "🔵",
        "name":             "CriptoVVIP",
        "desc":             "Средняя волатильность. Нужны крупные сделки чтобы сдвинуть цену.",
        "base_price":       500_00,
        "min_price":        100_00,
        "max_price":        50_000_00,
        "liquidity":        800_000,
        "max_trade_impact": 8.0,
        "reversion_speed":  0.020,
        "maker_strength":   0.5,
        "noise_pct":        2.0,
    },
    "CriptoWWIP": {
        "emoji":            "🟡",
        "name":             "CriptoWWIP",
        "desc":             "Самая дорогая монета. Устойчива к манипуляциям, медленный рост.",
        "base_price":       5_000_00,
        "min_price":        1_000_00,
        "max_price":        500_000_00,
        "liquidity":        4_000_000,
        "max_trade_impact": 3.0,
        "reversion_speed":  0.030,
        "maker_strength":   0.7,
        "noise_pct":        0.5,
    },
}

CRYPTO_CURRENCIES = list(CRYPTO_CONFIG.keys())


class CryptoService:

    # ── Инициализация цен ─────────────────────────────────────────────────────

    async def ensure_prices(self, session: AsyncSession) -> None:
        for currency, cfg in CRYPTO_CONFIG.items():
            r = await session.execute(
                select(CryptoPrice).where(CryptoPrice.currency == currency)
            )
            if not r.scalar_one_or_none():
                session.add(CryptoPrice(
                    currency=currency,
                    price_micro=cfg["base_price"],
                    buy_volume_micro=0,
                    sell_volume_micro=0,
                ))
        await session.flush()

    # ── Получить цены всех монет ──────────────────────────────────────────────

    async def get_all_prices(self, session: AsyncSession) -> dict[str, CryptoPrice]:
        r = await session.execute(select(CryptoPrice))
        rows = r.scalars().all()
        return {row.currency: row for row in rows}

    # ── Влияние сделки на цену ────────────────────────────────────────────────

    def _apply_price_impact(
        self,
        price_row: CryptoPrice,
        trade_value_nhcoins: int,
        is_buy: bool,
        cfg: dict,
    ) -> float:
        """
        Двигает price_row.price_micro и обновляет объём периода.
        Возвращает фактическое изменение цены в процентах (+ рост, - падение).
        """
        liquidity = cfg["liquidity"]
        max_impact = cfg["max_trade_impact"] / 100.0

        # Убывающее влияние: чем крупнее сделка относительно рынка — тем меньше %
        raw_impact = trade_value_nhcoins / (liquidity + trade_value_nhcoins)
        impact = min(raw_impact, max_impact)

        current = price_row.price_micro
        if is_buy:
            new_price = int(current * (1.0 + impact))
            price_row.buy_volume_micro += trade_value_nhcoins
        else:
            new_price = int(current * (1.0 - impact))
            price_row.sell_volume_micro += trade_value_nhcoins

        new_price = max(cfg["min_price"], min(cfg["max_price"], new_price))
        price_row.price_micro = new_price
        price_row.updated_at = datetime.now(timezone.utc)

        delta_pct = (new_price - current) / current * 100
        return delta_pct

    # ── Тик маркет-мейкера ────────────────────────────────────────────────────

    async def price_tick(self, session: AsyncSession) -> None:
        """Вызывается из планировщика каждые 5 минут.

        За каждый тик:
        1. Маркет-мейкер противодействует дисбалансу покупок/продаж.
        2. Мягкий возврат цены к базовому уровню (mean reversion).
        3. Случайный шум (эффект «живого» рынка).
        4. Сброс накопленных объёмов периода.
        """
        prices = await self.get_all_prices(session)

        for currency, cfg in CRYPTO_CONFIG.items():
            if currency not in prices:
                session.add(CryptoPrice(
                    currency=currency,
                    price_micro=cfg["base_price"],
                    buy_volume_micro=0,
                    sell_volume_micro=0,
                ))
                continue

            row = prices[currency]
            price = row.price_micro
            base  = cfg["base_price"]

            buy_vol  = row.buy_volume_micro  or 0
            sell_vol = row.sell_volume_micro or 0
            total_vol = buy_vol + sell_vol

            # 1. Маркет-мейкер: компенсирует дисбаланс спроса
            if total_vol > 0:
                net_pressure = buy_vol - sell_vol
                liquidity = cfg["liquidity"]
                pressure_ratio = net_pressure / (liquidity + abs(net_pressure))
                maker_adj = -pressure_ratio * cfg["maker_strength"]
                price = int(price * (1.0 + maker_adj))

            # 2. Mean reversion к базовой цене
            deviation = (price - base) / base
            reversion = -deviation * cfg["reversion_speed"]
            price = int(price * (1.0 + reversion))

            # 3. Случайный шум
            noise_range = cfg["noise_pct"] / 100.0
            noise = random.uniform(-noise_range, noise_range)
            price = int(price * (1.0 + noise))

            # Ограничиваем диапазоном
            price = max(cfg["min_price"], min(cfg["max_price"], price))
            row.price_micro = price
            row.updated_at = datetime.now(timezone.utc)

            # 4. Сброс объёмов периода
            row.buy_volume_micro  = 0
            row.sell_volume_micro = 0

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
    ) -> tuple[bool, str, float]:
        """
        Возвращает (ok, error_msg, price_delta_pct).
        price_delta_pct — насколько % сдвинулась цена после сделки.
        """
        if currency not in CRYPTO_CONFIG:
            return False, "❌ Неизвестная валюта.", 0.0
        if units <= 0:
            return False, "❌ Количество должно быть > 0.", 0.0

        prices = await self.get_all_prices(session)
        if currency not in prices:
            await self.ensure_prices(session)
            prices = await self.get_all_prices(session)

        cfg = CRYPTO_CONFIG[currency]
        price_row = prices[currency]
        price_micro = price_row.price_micro
        total_cost = (price_micro * units) // 100  # NHCoin

        if user.nh_coins < total_cost:
            return False, f"❌ Нужно {total_cost:,} NHCoin, у вас {user.nh_coins:,}.", 0.0

        user.nh_coins -= total_cost

        # Влияние на цену
        delta_pct = self._apply_price_impact(price_row, total_cost, is_buy=True, cfg=cfg)

        holding = await self.get_holding(session, user.id, currency)
        if holding:
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
        return True, "", delta_pct

    # ── Продать крипту ────────────────────────────────────────────────────────

    async def sell(
        self, session: AsyncSession, user: User, currency: str, units: int
    ) -> tuple[bool, str, float, int]:
        """
        Возвращает (ok, error_msg, price_delta_pct, revenue_nhcoins).
        revenue_nhcoins — фактическая выручка по цене до сделки.
        """
        if currency not in CRYPTO_CONFIG:
            return False, "❌ Неизвестная валюта.", 0.0, 0

        holding = await self.get_holding(session, user.id, currency)
        if not holding or holding.amount < units:
            return False, f"❌ Недостаточно {currency}.", 0.0, 0
        if units <= 0:
            return False, "❌ Количество должно быть > 0.", 0.0, 0

        prices = await self.get_all_prices(session)
        cfg = CRYPTO_CONFIG[currency]
        price_row = prices[currency]
        price_micro = price_row.price_micro
        gross = (price_micro * units) // 100
        commission = max(1, gross * SELL_COMMISSION_PCT // 100)
        revenue = gross - commission

        user.nh_coins += revenue

        # Влияние на цену считается по полной сумме до комиссии
        delta_pct = self._apply_price_impact(price_row, gross, is_buy=False, cfg=cfg)

        holding.amount -= units
        if holding.amount == 0:
            await session.delete(holding)

        await session.flush()
        return True, "", delta_pct, revenue


crypto_service = CryptoService()
