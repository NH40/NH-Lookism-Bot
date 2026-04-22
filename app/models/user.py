from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class User(Base):
    __tablename__ = "users"

    # ── Идентификация ──────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(256), nullable=False)
    gang_name: Mapped[str | None] = mapped_column(String(128))

    # ── Фаза и прогресс ────────────────────────────────────────────────────
    phase: Mapped[str] = mapped_column(String(16), nullable=False, default="gang")
    sector: Mapped[str | None] = mapped_column(String(4))
    gang_city_id: Mapped[int | None] = mapped_column(Integer)
    king_cities_count: Mapped[int] = mapped_column(Integer, default=0)
    fist_wins: Mapped[int] = mapped_column(Integer, default=0)
    fist_cities_count: Mapped[int] = mapped_column(Integer, default=0)

    # ── Ресурсы ────────────────────────────────────────────────────────────
    nh_coins: Mapped[int] = mapped_column(Integer, default=0)
    influence: Mapped[int] = mapped_column(Integer, default=100)
    combat_power: Mapped[int] = mapped_column(Integer, default=0)

    # ── Бизнес ────────────────────────────────────────────────────────────
    business_path: Mapped[str | None] = mapped_column(String(16))
    income_per_minute: Mapped[int] = mapped_column(Integer, default=0)

    # ── Бонусы к доходу ───────────────────────────────────────────────────
    income_bonus_percent: Mapped[int] = mapped_column(Integer, default=0)
    prestige_income_bonus: Mapped[int] = mapped_column(Integer, default=0)
    building_discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    district_multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    # ── Тикеты и гача ─────────────────────────────────────────────────────
    tickets: Mapped[int] = mapped_column(Integer, default=0)
    max_tickets: Mapped[int] = mapped_column(Integer, default=3)
    ticket_chance: Mapped[int] = mapped_column(Integer, default=25)
    ticket_cd_reduction: Mapped[int] = mapped_column(Integer, default=0)
    prestige_ticket_bonus: Mapped[int] = mapped_column(Integer, default=0)

    # ── Вербовка ──────────────────────────────────────────────────────────
    recruit_count_bonus: Mapped[int] = mapped_column(Integer, default=0)
    recruit_discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    double_recruit: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Тренировка ────────────────────────────────────────────────────────
    train_bonus_percent: Mapped[int] = mapped_column(Integer, default=0)
    train_quality_bonus: Mapped[int] = mapped_column(Integer, default=0)
    double_train: Mapped[bool] = mapped_column(Boolean, default=False)
    prestige_train_bonus: Mapped[int] = mapped_column(Integer, default=0)

    # ── Атака ─────────────────────────────────────────────────────────────
    double_attack: Mapped[bool] = mapped_column(Boolean, default=False)
    double_attack_used: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_attack_count: Mapped[int] = mapped_column(Integer, default=0)

    # ── Пробуждение (Престиж) ─────────────────────────────────────────────
    prestige_level: Mapped[int] = mapped_column(Integer, default=0)
    prestige_recruit_bonus: Mapped[int] = mapped_column(Integer, default=0)

    # ── Навыки — Путь ─────────────────────────────────────────────────────
    skill_path: Mapped[str | None] = mapped_column(String(16))
    skill_path_points: Mapped[int] = mapped_column(Integer, default=0)
    skill_path_bonus_multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    # ── Ультра Инстинкт ───────────────────────────────────────────────────
    ultra_instinct: Mapped[bool] = mapped_column(Boolean, default=False)
    true_ultra_instinct: Mapped[bool] = mapped_column(Boolean, default=False)
    ui_auto_recruit: Mapped[bool] = mapped_column(Boolean, default=True)
    ui_auto_train: Mapped[bool] = mapped_column(Boolean, default=True)
    ui_auto_ticket: Mapped[bool] = mapped_column(Boolean, default=True)
    ui_auto_pull: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Статистика для достижений ─────────────────────────────────────────
    total_wins: Mapped[int] = mapped_column(Integer, default=0)
    coins_spent: Mapped[int] = mapped_column(Integer, default=0)
    auction_wins: Mapped[int] = mapped_column(Integer, default=0)
    settings_opened: Mapped[int] = mapped_column(Integer, default=0)

    # ── Учитель/Ученик ────────────────────────────────────────────────────
    referred_by: Mapped[int | None] = mapped_column(Integer)
    teacher_power_bonus: Mapped[int] = mapped_column(Integer, default=0)
    teacher_income_share: Mapped[int] = mapped_column(Integer, default=3)

    # ── Настройки ─────────────────────────────────────────────────────────
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<User id={self.id} tg_id={self.tg_id} phase={self.phase}>"