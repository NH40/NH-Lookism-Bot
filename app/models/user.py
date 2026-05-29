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
    nh_coins: Mapped[int] = mapped_column(BigInteger, default=0)
    influence: Mapped[int] = mapped_column(BigInteger, default=100)
    combat_power: Mapped[int] = mapped_column(BigInteger, default=0, index=True)

    # ── Бизнес ────────────────────────────────────────────────────────────
    business_path: Mapped[str | None] = mapped_column(String(16))
    income_per_minute: Mapped[int] = mapped_column(BigInteger, default=0)

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

    # ── Карточки: пыль для крафта ────────────────────────────────────────
    card_dust: Mapped[int] = mapped_column(Integer, default=0)

    # ── Вербовка ──────────────────────────────────────────────────────────
    recruit_count_bonus: Mapped[int] = mapped_column(Integer, default=0)
    recruit_discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    double_recruit: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Тренировка ────────────────────────────────────────────────────────
    train_bonus_percent: Mapped[int] = mapped_column(Integer, default=0)
    train_quality_bonus: Mapped[int] = mapped_column(Integer, default=0)
    double_train: Mapped[bool] = mapped_column(Boolean, default=False)
    prestige_train_bonus: Mapped[int] = mapped_column(Integer, default=0)

    # ── Тикеты — двойная прокрутка ───────────────────────────────────────
    double_ticket: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Атака ─────────────────────────────────────────────────────────────
    double_attack: Mapped[bool] = mapped_column(Boolean, default=False)
    double_attack_used: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_attack_count: Mapped[int] = mapped_column(Integer, default=0)

    # ── Перемирие ─────────────────────────────────────────────────────────
    truce_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    truce_cd_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Пробуждение (Престиж) ─────────────────────────────────────────────
    prestige_level: Mapped[int] = mapped_column(Integer, default=0)
    prestige_recruit_bonus: Mapped[int] = mapped_column(Integer, default=0)

    # ── Очки мастерства (от Тома Ли) ─────────────────────────────────────
    mastery_points: Mapped[int] = mapped_column(Integer, default=0)

    # ── Навыки — Путь ─────────────────────────────────────────────────────
    skill_path: Mapped[str | None] = mapped_column(String(16))
    skill_path_points: Mapped[int] = mapped_column(Integer, default=0)
    skill_path_bonus_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    squad_power_bonus: Mapped[int] = mapped_column(Integer, default=0)   # % бонус к боевой мощи (путь Монстра)
    all_cd_reduction: Mapped[int] = mapped_column(Integer, default=0)    # % сокращение ВСЕХ КД (путь Тени)

    # ── Рейды ─────────────────────────────────────────────────────────────
    ui_fragments: Mapped[int] = mapped_column(Integer, default=0)
    alchemy_fragments: Mapped[int] = mapped_column(Integer, default=0)
    path_fragments: Mapped[int] = mapped_column(Integer, default=0)

    # ── Путь — дополнительные слоты ──────────────────────────────────────
    extra_path_skill_slots: Mapped[int] = mapped_column(Integer, default=1)

    # ── Путь — уровень и пробуждение ─────────────────────────────────────
    skill_path_level: Mapped[int] = mapped_column(Integer, default=0)
    path_awakened: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Максимальный шанс тикета ──────────────────────────────────────────
    max_ticket_chance: Mapped[int] = mapped_column(Integer, default=70)

    # ── Ультра Инстинкт (переработка) ────────────────────────────────────
    ui_level: Mapped[int] = mapped_column(Integer, default=0)        # 0-4
    ui_is_donat: Mapped[bool] = mapped_column(Boolean, default=False) # донатный = permanent

    # ── Ультра Инстинкт ───────────────────────────────────────────────────
    ultra_instinct: Mapped[bool] = mapped_column(Boolean, default=False)
    true_ultra_instinct: Mapped[bool] = mapped_column(Boolean, default=False)
    ui_auto_recruit: Mapped[bool] = mapped_column(Boolean, default=True)
    ui_auto_train: Mapped[bool] = mapped_column(Boolean, default=True)
    ui_auto_ticket: Mapped[bool] = mapped_column(Boolean, default=True)
    ui_auto_pull: Mapped[bool] = mapped_column(Boolean, default=False)
    donat_ui_potion: Mapped[bool] = mapped_column(Boolean, default=False)  # владение донатом
    ui_auto_potion: Mapped[bool] = mapped_column(Boolean, default=False)   # пользовательский тоггл
    donat_duel_cd: Mapped[bool] = mapped_column(Boolean, default=False)    # донат: -20% КД дуэлей

    # ── Статистика ────────────────────────────────────────────────────────
    total_wins: Mapped[int] = mapped_column(Integer, default=0)
    coins_spent: Mapped[int] = mapped_column(BigInteger, default=0)
    auction_wins: Mapped[int] = mapped_column(Integer, default=0)
    settings_opened: Mapped[int] = mapped_column(Integer, default=0)
    raid_boss_wins: Mapped[int] = mapped_column(Integer, default=0)           # убийства рейд-боссов
    total_statists_recruited: Mapped[int] = mapped_column(BigInteger, default=0)  # статистов завербовано всего
    daily_quests_completed: Mapped[int] = mapped_column(Integer, default=0)   # выполненных ежедневок
    market_sells: Mapped[int] = mapped_column(Integer, default=0)             # продаж на бирже

    # ── Учитель/Ученик ────────────────────────────────────────────────────
    referred_by: Mapped[int | None] = mapped_column(Integer)
    teacher_power_bonus: Mapped[int] = mapped_column(Integer, default=0)
    teacher_income_share: Mapped[int] = mapped_column(Integer, default=3)

    # ── КЛАНЫ ────────────────────────────────────────────────────
    clan_income_bonus: Mapped[int] = mapped_column(Integer, default=0)
    clan_ticket_bonus: Mapped[int] = mapped_column(Integer, default=0)
    clan_train_bonus: Mapped[int] = mapped_column(Integer, default=0)
    clan_donat_income_bonus: Mapped[int] = mapped_column(Integer, default=0)
    clan_donat_ticket_bonus: Mapped[int] = mapped_column(Integer, default=0)
    clan_donat_train_bonus: Mapped[int] = mapped_column(Integer, default=0)

    # ── VVIP (клановый, денормализовано) ─────────────────────────────────────
    clan_vvip_level: Mapped[int] = mapped_column(Integer, default=0)

    # ── Гений медицины (авто-зелья, новая система) ───────────────────────────
    med_genius_level: Mapped[int] = mapped_column(Integer, default=0)   # устарел, совместимость
    med_genius_donat: Mapped[bool] = mapped_column(Boolean, default=False)
    # Уровень каждого зелья: 0=заблокировано, 1-6=открыто (+5% к эффекту за каждый уровень)
    mg_level_power:     Mapped[int] = mapped_column(Integer, default=0)
    mg_level_training:  Mapped[int] = mapped_column(Integer, default=0)
    mg_level_income:    Mapped[int] = mapped_column(Integer, default=0)
    mg_level_luck:      Mapped[int] = mapped_column(Integer, default=0)
    mg_level_influence: Mapped[int] = mapped_column(Integer, default=0)
    mg_level_raid_drop: Mapped[int] = mapped_column(Integer, default=0)
    # Переключатели авто-зелий (вкл/выкл по желанию игрока)
    mg_auto_power: Mapped[bool] = mapped_column(Boolean, default=True)
    mg_auto_training: Mapped[bool] = mapped_column(Boolean, default=True)
    mg_auto_income: Mapped[bool] = mapped_column(Boolean, default=True)
    mg_auto_luck: Mapped[bool] = mapped_column(Boolean, default=True)
    mg_auto_influence: Mapped[bool] = mapped_column(Boolean, default=True)
    mg_auto_raid_drop: Mapped[bool] = mapped_column(Boolean, default=True)
    # Предпочитаемый уровень авто-покупки (0 = использовать максимальный доступный)
    mg_pref_power:     Mapped[int] = mapped_column(Integer, default=0)
    mg_pref_training:  Mapped[int] = mapped_column(Integer, default=0)
    mg_pref_income:    Mapped[int] = mapped_column(Integer, default=0)
    mg_pref_luck:      Mapped[int] = mapped_column(Integer, default=0)
    mg_pref_influence: Mapped[int] = mapped_column(Integer, default=0)
    mg_pref_raid_drop: Mapped[int] = mapped_column(Integer, default=0)

    # ── Пути: расширенные механики ────────────────────────────────────────────
    win_streak: Mapped[int] = mapped_column(Integer, default=0)
    path_unique_1: Mapped[bool] = mapped_column(Boolean, default=False)
    path_unique_2: Mapped[bool] = mapped_column(Boolean, default=False)
    shadow_stealth_active: Mapped[bool] = mapped_column(Boolean, default=False)  # toggle скрытности (path_unique_2)

    # ── Круговые донаты ───────────────────────────────────────────────────────
    circ_passive_income: Mapped[int] = mapped_column(BigInteger, default=0)  # NHCoin/час
    circ_defense_bonus: Mapped[int] = mapped_column(Integer, default=0)      # % снижения урона
    fragment_bonus_pct: Mapped[int] = mapped_column(Integer, default=0)      # % к дропу фрагментов
    circ_raid_bonus_pct: Mapped[int] = mapped_column(Integer, default=0)     # % бонус в рейдах
    circ_reflect_pct: Mapped[int] = mapped_column(Integer, default=0)        # % отражения урона
    circ_ticket_overflow: Mapped[bool] = mapped_column(Boolean, default=False)   # превышать лимит тикетов ×2
    circ_instant_raid_chance: Mapped[int] = mapped_column(Integer, default=0)    # % шанс мгновенного рейда
    circ_double_raid_chance: Mapped[int] = mapped_column(Integer, default=0)     # % шанс удвоения рейда
    circ_daily_districts: Mapped[int] = mapped_column(Integer, default=0)        # районов/день (Архангел)
    circ_dragon_active: Mapped[bool] = mapped_column(Boolean, default=False)     # спутник-дракон
    circ_clan_cashback: Mapped[bool] = mapped_column(Boolean, default=False)     # кешбек казны клана

    # ── Донат-валюта (NHDonate) ──────────────────────────────────────────────
    nh_donate: Mapped[int] = mapped_column(Integer, default=0)  # 1 NHDonate = 1 рубль

    # ── Бонус влияния от донатного сета (strongest_0gen) ─────────────────────
    # Хранит АДДИТИВНУЮ прибавку к influence, добавленную сет-бонусом.
    # При reapply_all_titles вычитается и пересчитывается, чтобы не множился
    # экспоненциально при каждом вызове.
    influence_donat_bonus: Mapped[int] = mapped_column(BigInteger, default=0)

    # ── Бан ───────────────────────────────────────────────────────────────
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    ban_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ban_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # ── Настройки ─────────────────────────────────────────────────────────
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notif_pvp: Mapped[bool] = mapped_column(Boolean, default=True)
    notif_auction: Mapped[bool] = mapped_column(Boolean, default=True)
    notif_cities: Mapped[bool] = mapped_column(Boolean, default=True)
    notif_clan_war: Mapped[bool] = mapped_column(Boolean, default=True)
    notif_boss: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} tg_id={self.tg_id} phase={self.phase}>"