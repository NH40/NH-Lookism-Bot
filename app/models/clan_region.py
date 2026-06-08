from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class KoreanRegion(Base):
    """Статический справочник 16 регионов Кореи (инициализируется один раз)."""
    __tablename__ = "korean_regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    emoji: Mapped[str] = mapped_column(String(8), nullable=False)

    # Бонусы главе клана-владельца (%)
    owner_income_pct: Mapped[int] = mapped_column(Integer, default=0)
    owner_train_pct: Mapped[int] = mapped_column(Integer, default=0)
    owner_ticket_pct: Mapped[int] = mapped_column(Integer, default=0)
    owner_power_pct: Mapped[int] = mapped_column(Integer, default=0)

    # Бонусы всем участникам клана-владельца (%)
    member_income_pct: Mapped[int] = mapped_column(Integer, default=0)
    member_train_pct: Mapped[int] = mapped_column(Integer, default=0)
    member_ticket_pct: Mapped[int] = mapped_column(Integer, default=0)
    member_power_pct: Mapped[int] = mapped_column(Integer, default=0)

    description: Mapped[str] = mapped_column(String(256), nullable=False, default="")

    # Клан-владелец (NULL = никто не владеет)
    owner_clan_id: Mapped[int | None] = mapped_column(Integer, index=True)


class KoreanRegionWar(Base):
    """Активная война за регион. Один активный экземпляр на регион."""
    __tablename__ = "korean_region_wars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    initiator_clan_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_finished: Mapped[bool] = mapped_column(Boolean, default=False)
    winner_clan_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class KoreanRegionWarParticipant(Base):
    """Участие клана в войне за регион + накопленные очки активности."""
    __tablename__ = "korean_region_war_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    war_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    clan_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Сумма очков активности всех игроков клана
    score: Mapped[int] = mapped_column(Integer, default=0)


class KoreanRegionActivity(Base):
    """Вклад конкретного игрока в активную войну за регион.

    Каждое действие можно делать много раз (до капа), каждое даёт очки.
    action        | pts/раз | кап | макс
    train         |   1     | 10  |  10
    attack_gang   |   2     |  5  |  10
    attack_king   |   3     |  5  |  15
    attack_fist   |   4     |  3  |  12
    spend         |   1     | 10  |  10
    raid          |   3     |  5  |  15
    recruit       |   1     | 10  |  10
    Макс на игрока: 82 очка
    """
    __tablename__ = "korean_region_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    war_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    clan_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Счётчики действий
    train_count:       Mapped[int] = mapped_column(Integer, default=0)  # тренировка +1×10
    attack_gang_count: Mapped[int] = mapped_column(Integer, default=0)  # атака gang +2×5
    attack_king_count: Mapped[int] = mapped_column(Integer, default=0)  # атака king +3×5
    attack_fist_count: Mapped[int] = mapped_column(Integer, default=0)  # атака fist +4×3
    spend_count:       Mapped[int] = mapped_column(Integer, default=0)  # трата монет +1×10
    raid_count:        Mapped[int] = mapped_column(Integer, default=0)  # рейд-босс +3×5
    recruit_count:     Mapped[int] = mapped_column(Integer, default=0)  # найм статиста +1×10
    auction_count:     Mapped[int] = mapped_column(Integer, default=0)  # аукцион +2×5
    duel_count:        Mapped[int] = mapped_column(Integer, default=0)  # дуэль +3×5
    market_count:      Mapped[int] = mapped_column(Integer, default=0)  # биржа +1×5
    campaign_count:    Mapped[int] = mapped_column(Integer, default=0)  # поход +4×3
    boss_count:        Mapped[int] = mapped_column(Integer, default=0)  # босс +3×5
    quest_count:       Mapped[int] = mapped_column(Integer, default=0)  # задание +2×5
    bank_count:        Mapped[int] = mapped_column(Integer, default=0)  # банк +1×5

    # Старые boolean-поля (оставляем для совместимости, больше не используются)
    did_train: Mapped[bool] = mapped_column(Boolean, default=False)
    did_attack_gang: Mapped[bool] = mapped_column(Boolean, default=False)
    did_attack_king: Mapped[bool] = mapped_column(Boolean, default=False)
    did_attack_fist: Mapped[bool] = mapped_column(Boolean, default=False)
    did_spend: Mapped[bool] = mapped_column(Boolean, default=False)
    did_raid: Mapped[bool] = mapped_column(Boolean, default=False)
    did_recruit: Mapped[bool] = mapped_column(Boolean, default=False)

    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
