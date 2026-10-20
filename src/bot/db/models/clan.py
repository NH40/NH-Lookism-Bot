"""Кланы (дизайн — `docs/design/clans.md`). Ядро — как в Universe Anime Planet (клан,
участники, заявки/приглашения), сверху — земли, здания, казна, клановая рота, войны за земли,
журнал и доля дохода владельца/зама."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class Clan(Base):
    __tablename__ = "clans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Аватарка — Telegram file_id (присылает сам игрок; только топ-10 кланов, как в UAP).
    image_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    lands: Mapped[int] = mapped_column(Integer, nullable=False, default=8, server_default="8", index=True)
    treasury: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    # Донат-уровень 0–5 (+4 к потолку земель и бафы; покупка — с доменом доната).
    donate_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Тикеты из клан-магазина за сутки (МСК) — для растущей цены и дневного лимита (2026-10-21).
    shop_tickets_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    shop_tickets_bought: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_attack_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shield_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ClanMember(Base):
    """Игрок состоит максимум в одном клане — `user_id` и есть PK."""

    __tablename__ = "clan_members"
    __table_args__ = (
        # Максимум один владелец и один заместитель на клан — на уровне БД (как в UAP).
        Index("uq_clan_members_owner_deputy", "clan_id", "rank", unique=True, postgresql_where="rank IN ('owner', 'deputy')"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    clan_id: Mapped[int] = mapped_column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), index=True, nullable=False)
    rank: Mapped[str] = mapped_column(String(8), nullable=False, default="member", server_default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Доступ к клановой роте для рядового участника (пользователь 2026-10-04): первый раз забрать
    # бойцов можно только с одобрения владельца или заместителя; одобрили один раз — дальше без
    # подтверждения. Капитан и старше — без одобрения. `garrison_request_at` — ждущий запрос.
    garrison_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    garrison_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClanJoinRequest(Base):
    """Заявка игрока в клан и приглашение клана игроку — одна таблица, направление — `is_invite`."""

    __tablename__ = "clan_join_requests"
    __table_args__ = (UniqueConstraint("clan_id", "user_id", name="uq_clan_join_requests"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clan_id: Mapped[int] = mapped_column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    is_invite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ClanBuilding(Base):
    """Здания на землях клана — число по виду (здания одного вида взаимозаменяемы)."""

    __tablename__ = "clan_buildings"

    clan_id: Mapped[int] = mapped_column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class ClanGarrisonExtra(Base):
    """Клановая рота: статисты (ключ стопки без лагеря)."""

    __tablename__ = "clan_garrison_extras"

    clan_id: Mapped[int] = mapped_column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), primary_key=True)
    rank: Mapped[str] = mapped_column(String(16), primary_key=True)
    stars: Mapped[int] = mapped_column(Integer, primary_key=True)
    training_level: Mapped[int] = mapped_column(Integer, primary_key=True)
    school: Mapped[str] = mapped_column(String(8), primary_key=True)
    school_level: Mapped[int] = mapped_column(Integer, primary_key=True)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")


class ClanContract(Base):
    """Контрактники в клановой роте (пользователь 2026-10-12: вместо вечных наёмников из магазина
    клана). Воюют за роту и гибнут, по сроку уходят; забрать себе их не может никто — они не в
    `clan_garrison_extras`, а здесь."""

    __tablename__ = "clan_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clan_id: Mapped[int] = mapped_column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), index=True, nullable=False)
    rank: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class ClanGarrisonCard(Base):
    """Клановая рота: уники."""

    __tablename__ = "clan_garrison_cards"

    clan_id: Mapped[int] = mapped_column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), primary_key=True)
    card_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")


class ClanWar(Base):
    """История войн кланов (сама война — мгновенный бой рот)."""

    __tablename__ = "clan_wars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attacker_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clans.id", ondelete="SET NULL"), index=True, nullable=True)
    defender_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clans.id", ondelete="SET NULL"), index=True, nullable=True)
    attacker_name: Mapped[str] = mapped_column(String(32), nullable=False)
    defender_name: Mapped[str] = mapped_column(String(32), nullable=False)
    attacker_won: Mapped[bool] = mapped_column(Boolean, nullable=False)
    lands_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    treasury_taken: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    attacker_power: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    defender_power: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    attacker_dead: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    defender_dead: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)


class ClanDonatePurchase(Base):
    """Купленный донат-уровень клана: кто и сколько заплатил. `clans.donate_level` = число строк.
    Купивший ушёл — строка удаляется, уплаченное возвращается ему (`services/clan/economy`)."""

    __tablename__ = "clan_donate_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clan_id: Mapped[int] = mapped_column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ClanLog(Base):
    """Журнал клана: казна, рота, стройка, война — кто и что."""

    __tablename__ = "clan_log"
    __table_args__ = (Index("ix_clan_log_clan_created", "clan_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clan_id: Mapped[int] = mapped_column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ClanIncomeShare(Base):
    """Накопленная доля дохода участников для владельца/зама (1% с каждого зачисления).
    Отдельная таблица, а не колонка `users`: начисление идёт внутри чужой транзакции
    дохода — строка получателя здесь не пересекается с блокировками строк `users`."""

    __tablename__ = "clan_income_shares"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    pending: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")



class ClanMemberStat(Base):
    """Вклад участника в клан — накопительные счётчики (пользователь 2026-10-21: «статистика,
    чтобы смотреть эффективность игроков для клана: вклад в казну, роту, магазин, войны»).
    Ключ — (клан, игрок): ушёл и вернулся — счёт продолжается; в другом клане — с нуля.
    Растёт только через `repositories/clan.bump_stats` внутри транзакции самого действия."""

    __tablename__ = "clan_member_stats"

    clan_id: Mapped[int] = mapped_column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    treasury: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")  # 🪙 внесено в казну
    garrison_units: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")  # бойцов отдано в роту
    garrison_power: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")  # их мощь
    garrison_taken: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")  # бойцов забрано из роты
    shop_spent: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")  # из казны на магазин
    build_spent: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")  # из казны на земли/здания
    wars: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")  # атак проведено
    wars_won: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lands_won: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")  # земель взято в атаках
    exchanges: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")  # передач через обменник
