from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector: Mapped[str | None] = mapped_column(String(4), index=True)  # DEPRECATED — заменено на country (патч 1.3.1)
    country: Mapped[str | None] = mapped_column(String(32), index=True)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    type_id: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=4р, 2=8р, 3=16р, 4=32р, 5=64р
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    total_districts: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_districts: Mapped[int] = mapped_column(Integer, default=0)
    is_fully_captured: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[int | None] = mapped_column(Integer)  # FK → users
    district_power_multiplier: Mapped[float] = mapped_column(Float, default=1.0)


class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_id: Mapped[int | None] = mapped_column(Integer, index=True)
    is_captured: Mapped[bool] = mapped_column(Boolean, default=False)
    # Постоянная привязка дохода — кто "исторически" заработал этот район.
    # НЕ сбрасывается при повышении фазы (банда→король→император): владелец
    # продолжает получать с него бизнес-доход навсегда. owner_id/is_captured —
    # ЭТО ОТДЕЛЬНО: текущий держатель района для боевой фазы Банды, который
    # свободно переходит другим игрокам в бою, не трогая income_owner_id.
    # Одна и та же победа над районом засчитывается ОБОИМ: и текущему
    # захватчику (owner_id, для его прогресса Банды), и историческому
    # владельцу (income_owner_id, для его бизнес-дохода) — см.
    # city_repo.get_user_district_count.
    income_owner_id: Mapped[int | None] = mapped_column(Integer, index=True)


class FistBot(Base):
    __tablename__ = "fist_bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # power_ratio: multiplier relative to challenger's power when bot is created
    power_ratio: Mapped[float] = mapped_column(Float, default=1.0)
    base_power: Mapped[int] = mapped_column(BigInteger, default=0)
    current_power: Mapped[int] = mapped_column(BigInteger, default=0)
    defeat_count: Mapped[int] = mapped_column(Integer, default=0)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Linked to a specific user challenge session
    challenger_id: Mapped[int | None] = mapped_column(Integer, index=True)