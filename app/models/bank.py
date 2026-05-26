"""
Банк: кредиты, хранилища, криптовалюты, инвестиции.
"""
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


# ─── Кредиты ──────────────────────────────────────────────────────────────────

class BankCredit(Base):
    """Кредит игрока. Сохраняется через снос банды и престиж; удаляется только патчем."""
    __tablename__ = "bank_credits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)       # сумма кредита
    due_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)   # к выплате (125%)
    paid_amount: Mapped[int] = mapped_column(BigInteger, default=0)       # уже выплачено

    taken_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    block_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)   # +3h
    delete_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # +6h

    # Статус
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    is_gang_deleted: Mapped[bool] = mapped_column(Boolean, default=False)  # банда уже снесена

    # Уведомления
    notif_block_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    notif_delete_sent: Mapped[bool] = mapped_column(Boolean, default=False)


# ─── Криптовалюта: мировой курс ───────────────────────────────────────────────

class CryptoPrice(Base):
    """Текущий курс криптовалюты (одна запись на монету)."""
    __tablename__ = "crypto_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    currency: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    # price хранится в "микро-NHCoin" (×100) чтобы точно считать дроби
    price_micro: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ─── Криптовалюта: холдинги игрока ────────────────────────────────────────────

class CryptoHolding(Base):
    """Запас криптовалюты у одного игрока."""
    __tablename__ = "crypto_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)

    # Количество монет (в «единицах крипты», дробные не нужны)
    amount: Mapped[int] = mapped_column(BigInteger, default=0)
    # Средняя цена покупки (micro), для статистики
    avg_buy_price_micro: Mapped[int] = mapped_column(BigInteger, default=0)


# ─── Ячейки хранилища ─────────────────────────────────────────────────────────

class StorageCell(Base):
    """
    Ячейка хранилища (5 штук). Сохраняет предмет через снос банды.
    Требует ежеминутную плату; при нулевом балансе содержимое удаляется.
    """
    __tablename__ = "storage_cells"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)            # 1–5

    is_open: Mapped[bool] = mapped_column(Boolean, default=False)         # куплена ли ячейка
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Содержимое ячейки (nullable если пусто)
    item_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # JSON: {"amount": N} для ресурсов, {"char_id": ..., "level": ...} для карт, и т.д.
    item_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_fee_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fee_debt: Mapped[int] = mapped_column(BigInteger, default=0)   # накопленный долг по плате


# ─── Инвестиции ───────────────────────────────────────────────────────────────

class Investment(Base):
    """Банковский вклад игрока."""
    __tablename__ = "bank_investments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False)    # 1/3/6/12/24
    interest_pct: Mapped[int] = mapped_column(Integer, nullable=False)      # 3/5/10/15/20

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    matures_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    is_matured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_withdrawn: Mapped[bool] = mapped_column(Boolean, default=False)
    notif_sent: Mapped[bool] = mapped_column(Boolean, default=False)
