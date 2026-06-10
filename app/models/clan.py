from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Clan(Base):
    __tablename__ = "clans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    combat_power: Mapped[int] = mapped_column(BigInteger, default=0)
    treasury: Mapped[int] = mapped_column(BigInteger, default=0)
    max_members: Mapped[int] = mapped_column(Integer, default=5)
    # Улучшения (за NHCoin из казны)
    bonus_max_members: Mapped[int] = mapped_column(Integer, default=0)
    bonus_income_pct: Mapped[int] = mapped_column(Integer, default=0)
    bonus_ticket_pct: Mapped[int] = mapped_column(Integer, default=0)
    bonus_train_pct: Mapped[int] = mapped_column(Integer, default=0)
    # Казна очков активности (ОА) и улучшения за ОА
    treasury_ap: Mapped[int] = mapped_column(Integer, default=0)
    ap_income_circles: Mapped[int] = mapped_column(Integer, default=0)
    ap_train_circles: Mapped[int] = mapped_column(Integer, default=0)
    ap_ticket_circles: Mapped[int] = mapped_column(Integer, default=0)
    # Донат-бонусы (выдаются администратором)
    donat_income_pct: Mapped[int] = mapped_column(Integer, default=0)
    donat_ticket_pct: Mapped[int] = mapped_column(Integer, default=0)
    donat_train_pct: Mapped[int] = mapped_column(Integer, default=0)
    vvip_level: Mapped[int] = mapped_column(Integer, default=0)
    # Счётчики кругов по каждому донат-пакету (макс 5 каждый)
    donat_wealth_circles: Mapped[int] = mapped_column(Integer, default=0)
    donat_luck_circles: Mapped[int] = mapped_column(Integer, default=0)
    donat_school_circles: Mapped[int] = mapped_column(Integer, default=0)
    donat_war_circles: Mapped[int] = mapped_column(Integer, default=0)
    donat_premium_circles: Mapped[int] = mapped_column(Integer, default=0)
    # КД после войны регион-vs-регион (4 часа, нельзя вызывать/быть вызванным)
    region_war_cd_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ClanMember(Base):
    __tablename__ = "clan_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clan_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    # owner / deputy / captain / member
    rank: Mapped[str] = mapped_column(String(16), nullable=False, default="member")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ClanInvite(Base):
    __tablename__ = "clan_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clan_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    from_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    to_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    invite_type: Mapped[str] = mapped_column(String(16), default="invite")
    # invite = владелец приглашает, request = игрок просится
    is_pending: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ClanWar(Base):
    __tablename__ = "clan_wars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clan1_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    clan2_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    war_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # power = война вооружения, treasury = война богатств
    clan1_start: Mapped[int] = mapped_column(BigInteger, default=0)
    clan2_start: Mapped[int] = mapped_column(BigInteger, default=0)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_finished: Mapped[bool] = mapped_column(Boolean, default=False)
    winner_clan_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ClanAuction(Base):
    __tablename__ = "clan_auctions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clan_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    reward_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reward_data: Mapped[str | None] = mapped_column(String(256))
    current_bid: Mapped[int] = mapped_column(BigInteger, default=0)
    leader_id: Mapped[int | None] = mapped_column(Integer)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_finished: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )