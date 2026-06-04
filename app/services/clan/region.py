from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update as sa_update

from app.models.clan import Clan, ClanMember
from app.models.clan_region import (
    KoreanRegion,
    KoreanRegionWar,
    KoreanRegionWarParticipant,
    KoreanRegionActivity,
)
from app.services.clan.base import ClanBaseService

# Ограничение участников клана для войны за регион
REGION_WAR_MAX_MEMBERS = 15
# Минимальный порог очков для захвата региона (макс на игрока = 82, макс на клан = 15×82 = 1230)
REGION_WAR_MIN_SCORE = 100
# Продолжительность войны в часах
REGION_WAR_HOURS = 6

RANK_LABELS = {
    "owner": "👑 Владелец",
    "deputy": "🛡 Заместитель",
    "captain": "⚔️ Капитан",
    "member": "👤 Участник",
}

# Ранги, которые могут управлять войной (начать/отменить)
WAR_ALLOWED_RANKS = {"owner", "deputy"}


class ClanRegionService(ClanBaseService):

    # ── Геттеры ────────────────────────────────────────────────────────────────

    async def get_all_regions(self, session: AsyncSession) -> list[KoreanRegion]:
        result = await session.execute(select(KoreanRegion).order_by(KoreanRegion.id))
        return list(result.scalars().all())

    async def get_region_by_slug(self, session: AsyncSession, slug: str) -> KoreanRegion | None:
        return await session.scalar(select(KoreanRegion).where(KoreanRegion.slug == slug))

    async def get_region_by_id(self, session: AsyncSession, region_id: int) -> KoreanRegion | None:
        return await session.scalar(select(KoreanRegion).where(KoreanRegion.id == region_id))

    async def get_clan_region(self, session: AsyncSession, clan_id: int) -> KoreanRegion | None:
        """Возвращает регион, которым владеет клан (или None)."""
        return await session.scalar(
            select(KoreanRegion).where(KoreanRegion.owner_clan_id == clan_id)
        )

    async def get_active_war_for_region(
        self, session: AsyncSession, region_id: int
    ) -> KoreanRegionWar | None:
        return await session.scalar(
            select(KoreanRegionWar).where(
                KoreanRegionWar.region_id == region_id,
                KoreanRegionWar.is_finished == False,
            )
        )

    async def get_active_war_for_clan(
        self, session: AsyncSession, clan_id: int
    ) -> KoreanRegionWar | None:
        """Активная война, в которой участвует клан (как инициатор или участник)."""
        # Проверяем как инициатор
        war = await session.scalar(
            select(KoreanRegionWar).where(
                KoreanRegionWar.initiator_clan_id == clan_id,
                KoreanRegionWar.is_finished == False,
            )
        )
        if war:
            return war
        # Проверяем как присоединившийся
        participant = await session.scalar(
            select(KoreanRegionWarParticipant).where(
                KoreanRegionWarParticipant.clan_id == clan_id,
            ).join(
                KoreanRegionWar,
                and_(
                    KoreanRegionWar.id == KoreanRegionWarParticipant.war_id,
                    KoreanRegionWar.is_finished == False,
                )
            )
        )
        if participant:
            return await session.scalar(
                select(KoreanRegionWar).where(KoreanRegionWar.id == participant.war_id)
            )
        return None

    async def get_war_participants(
        self, session: AsyncSession, war_id: int
    ) -> list[KoreanRegionWarParticipant]:
        result = await session.execute(
            select(KoreanRegionWarParticipant)
            .where(KoreanRegionWarParticipant.war_id == war_id)
            .order_by(KoreanRegionWarParticipant.score.desc())
        )
        return list(result.scalars().all())

    async def get_member_rank(self, session: AsyncSession, clan_id: int, user_id: int) -> str | None:
        """Возвращает ранг участника или None если не в клане."""
        member = await session.scalar(
            select(ClanMember).where(
                ClanMember.clan_id == clan_id,
                ClanMember.user_id == user_id,
            )
        )
        return member.rank if member else None

    # ── Ранги ──────────────────────────────────────────────────────────────────

    async def set_member_rank(
        self, session: AsyncSession, clan: Clan, requester_id: int, target_user_id: int, new_rank: str
    ) -> dict:
        if new_rank not in ("deputy", "captain", "member"):
            return {"ok": False, "reason": "Недопустимый ранг"}

        # Только владелец клана может менять ранги
        if clan.owner_id != requester_id:
            return {"ok": False, "reason": "Только владелец может менять ранги"}

        if target_user_id == requester_id:
            return {"ok": False, "reason": "Нельзя изменить собственный ранг"}

        member = await session.scalar(
            select(ClanMember).where(
                ClanMember.clan_id == clan.id,
                ClanMember.user_id == target_user_id,
            )
        )
        if not member:
            return {"ok": False, "reason": "Игрок не в вашем клане"}

        member.rank = new_rank
        await session.flush()
        return {"ok": True, "rank": new_rank}

    # ── Война за регион ────────────────────────────────────────────────────────

    async def start_region_war(
        self, session: AsyncSession, clan: Clan, region: KoreanRegion, requester_id: int
    ) -> dict:
        rank = await self.get_member_rank(session, clan.id, requester_id)
        if rank not in WAR_ALLOWED_RANKS:
            return {"ok": False, "reason": "Только владелец или заместитель может начать войну"}

        members = await self.get_clan_members(session, clan.id)
        if len(members) > REGION_WAR_MAX_MEMBERS:
            return {
                "ok": False,
                "reason": f"Клан не может участвовать в войне за регион при более {REGION_WAR_MAX_MEMBERS} участниках. "
                          f"У вас {len(members)}.",
            }

        # Проверяем, не участвует ли клан уже в какой-либо войне за регион
        existing = await self.get_active_war_for_clan(session, clan.id)
        if existing:
            return {"ok": False, "reason": "Ваш клан уже участвует в войне за регион"}

        # Проверяем, нет ли уже активной войны за этот регион
        active_war = await self.get_active_war_for_region(session, region.id)
        if active_war:
            # Разрешаем присоединиться к войне
            return await self.join_region_war(session, clan, active_war, requester_id)

        # Ваш клан уже владеет этим регионом
        if region.owner_clan_id == clan.id:
            return {"ok": False, "reason": "Ваш клан уже владеет этим регионом"}

        # Проверяем, нет ли у клана уже другого региона
        own_region = await self.get_clan_region(session, clan.id)
        if own_region:
            return {
                "ok": False,
                "reason": f"Ваш клан уже владеет регионом {own_region.emoji} {own_region.name}. "
                          "Один клан — один регион.",
            }

        now = datetime.now(timezone.utc)
        war = KoreanRegionWar(
            region_id=region.id,
            initiator_clan_id=clan.id,
            ends_at=now + timedelta(hours=REGION_WAR_HOURS),
        )
        session.add(war)
        await session.flush()

        participant = KoreanRegionWarParticipant(
            war_id=war.id,
            clan_id=clan.id,
            score=0,
        )
        session.add(participant)
        await session.flush()

        return {"ok": True, "war_id": war.id, "ends_at": war.ends_at, "joined": False}

    async def join_region_war(
        self, session: AsyncSession, clan: Clan, war: KoreanRegionWar, requester_id: int
    ) -> dict:
        rank = await self.get_member_rank(session, clan.id, requester_id)
        if rank not in WAR_ALLOWED_RANKS:
            return {"ok": False, "reason": "Только владелец или заместитель может присоединиться к войне"}

        members = await self.get_clan_members(session, clan.id)
        if len(members) > REGION_WAR_MAX_MEMBERS:
            return {
                "ok": False,
                "reason": f"Клан не может участвовать при более {REGION_WAR_MAX_MEMBERS} участниках",
            }

        own_region = await self.get_clan_region(session, clan.id)
        if own_region:
            return {"ok": False, "reason": "Клан уже владеет регионом. Один клан — один регион."}

        existing = await self.get_active_war_for_clan(session, clan.id)
        if existing:
            return {"ok": False, "reason": "Клан уже участвует в другой войне за регион"}

        # Проверяем, не участвует ли уже в этой войне
        already = await session.scalar(
            select(KoreanRegionWarParticipant).where(
                KoreanRegionWarParticipant.war_id == war.id,
                KoreanRegionWarParticipant.clan_id == clan.id,
            )
        )
        if already:
            return {"ok": False, "reason": "Клан уже участвует в этой войне"}

        participant = KoreanRegionWarParticipant(
            war_id=war.id,
            clan_id=clan.id,
            score=0,
        )
        session.add(participant)
        await session.flush()

        return {"ok": True, "war_id": war.id, "ends_at": war.ends_at, "joined": True}

    # ── Активность игрока ──────────────────────────────────────────────────────

    async def record_activity(
        self,
        session: AsyncSession,
        user_id: int,
        clan_id: int,
        action: str,  # "train" | "attack_gang" | "attack_king" | "attack_fist" | "spend"
    ) -> None:
        """Фиксирует активность игрока в текущей войне клана.

        Безопасно вызывать из любого хендлера — если войны нет, просто ничего не делает.
        """
        war = await self.get_active_war_for_clan(session, clan_id)
        if not war:
            return

        activity = await session.scalar(
            select(KoreanRegionActivity).where(
                KoreanRegionActivity.war_id == war.id,
                KoreanRegionActivity.user_id == user_id,
            )
        )
        if not activity:
            activity = KoreanRegionActivity(
                war_id=war.id,
                user_id=user_id,
                clan_id=clan_id,
            )
            session.add(activity)
            await session.flush()

        # action → (count_field, pts_per_action, max_count)
        action_map = {
            "train":        ("train_count",       1, 10),
            "attack_gang":  ("attack_gang_count", 2,  5),
            "attack_king":  ("attack_king_count", 3,  5),
            "attack_fist":  ("attack_fist_count", 4,  3),
            "spend":        ("spend_count",        1, 10),
            "raid":         ("raid_count",         3,  5),
            "recruit":      ("recruit_count",      1, 10),
            "auction":      ("auction_count",      2,  5),
            "duel":         ("duel_count",         3,  5),
            "market":       ("market_count",       1,  5),
            "campaign":     ("campaign_count",     4,  3),
            "boss":         ("boss_count",         3,  5),
            "quest":        ("quest_count",        2,  5),
            "bank":         ("bank_count",         1,  5),
        }
        entry = action_map.get(action)
        if not entry:
            return
        count_field, pts, cap = entry

        current = getattr(activity, count_field, 0)
        if current >= cap:
            return  # кап достигнут

        setattr(activity, count_field, current + 1)

        # Добавляем очки участнику
        participant = await session.scalar(
            select(KoreanRegionWarParticipant).where(
                KoreanRegionWarParticipant.war_id == war.id,
                KoreanRegionWarParticipant.clan_id == clan_id,
            )
        )
        if participant:
            participant.score += pts
        await session.flush()

    # ── Завершение войн ────────────────────────────────────────────────────────

    async def finish_expired_region_wars(self, session: AsyncSession) -> list[dict]:
        """Завершает просроченные войны за регионы и передаёт владение."""
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(KoreanRegionWar).where(
                KoreanRegionWar.is_finished == False,
                KoreanRegionWar.ends_at <= now,
            )
        )
        wars = list(result.scalars().all())
        outcomes = []
        for war in wars:
            outcome = await self._resolve_war(session, war)
            outcomes.append(outcome)
        return outcomes

    async def _resolve_war(self, session: AsyncSession, war: KoreanRegionWar) -> dict:
        region = await self.get_region_by_id(session, war.region_id)
        if not region:
            war.is_finished = True
            return {"ok": False}

        participants = await self.get_war_participants(session, war.id)

        if not participants:
            war.is_finished = True
            await session.flush()
            return {"ok": False, "reason": "no_participants"}

        # Победитель — участник с наибольшим счётом
        best = max(participants, key=lambda p: p.score)

        war.is_finished = True

        if best.score < REGION_WAR_MIN_SCORE:
            # Никто не набрал минимальный порог — регион остаётся без владельца
            war.winner_clan_id = None
            if region.owner_clan_id:
                await self.clear_region_bonuses_for_clan(session, region.owner_clan_id)
                region.owner_clan_id = None
            await session.flush()
            return {
                "ok": True,
                "winner_clan_id": None,
                "region_id": region.id,
                "region_name": region.name,
                "best_score": best.score,
                "min_score": REGION_WAR_MIN_SCORE,
            }

        prev_owner_clan_id = region.owner_clan_id
        war.winner_clan_id = best.clan_id
        region.owner_clan_id = best.clan_id
        await session.flush()

        # Снимаем бонусы у предыдущего владельца, применяем победителю
        if prev_owner_clan_id and prev_owner_clan_id != best.clan_id:
            await self.clear_region_bonuses_for_clan(session, prev_owner_clan_id)
        await self.apply_region_bonuses_for_clan(session, best.clan_id, region)

        return {
            "ok": True,
            "winner_clan_id": best.clan_id,
            "prev_owner_clan_id": prev_owner_clan_id,
            "region_id": region.id,
            "region_name": region.name,
            "region_emoji": region.emoji,
            "winner_score": best.score,
        }

    # ── Применение/сброс бонусов региона на игроков ───────────────────────────

    @staticmethod
    def _set_region_bonuses(user: "User", cfg, is_owner: bool) -> None:
        o = is_owner
        user.region_income_pct          = cfg.owner_income_pct          if o else cfg.member_income_pct
        user.region_ticket_pct          = 0
        user.region_power_pct           = 0
        user.region_passive_income      = cfg.owner_passive_income      if o else cfg.member_passive_income
        user.region_war_genius          = cfg.owner_war_genius          if o else cfg.member_war_genius
        user.region_train_cd_pct        = cfg.owner_train_cd_pct        if o else cfg.member_train_cd_pct
        user.region_raid_cd_pct         = cfg.owner_raid_cd_pct         if o else cfg.member_raid_cd_pct
        user.region_fragment_pct        = cfg.owner_fragment_pct        if o else cfg.member_fragment_pct
        user.region_squad_power_pct     = cfg.owner_squad_power_pct     if o else cfg.member_squad_power_pct
        user.region_char_power_pct      = cfg.owner_char_power_pct      if o else cfg.member_char_power_pct
        user.region_ticket_overflow     = cfg.owner_ticket_overflow      if o else cfg.member_ticket_overflow
        user.region_double_ticket       = cfg.owner_double_ticket        if o else cfg.member_double_ticket
        user.region_raid_damage_pct     = cfg.owner_raid_damage_pct     if o else cfg.member_raid_damage_pct
        user.region_income_building_pct = cfg.owner_income_building_pct if o else cfg.member_income_building_pct
        user.region_trainer_discount    = cfg.owner_trainer_discount    if o else cfg.member_trainer_discount

    @staticmethod
    def _zero_region_bonuses(user: "User") -> None:
        user.region_income_pct          = 0
        user.region_ticket_pct          = 0
        user.region_power_pct           = 0
        user.region_passive_income      = 0
        user.region_war_genius          = 0
        user.region_train_cd_pct        = 0
        user.region_raid_cd_pct         = 0
        user.region_fragment_pct        = 0
        user.region_squad_power_pct     = 0
        user.region_char_power_pct      = 0
        user.region_ticket_overflow     = False
        user.region_double_ticket       = False
        user.region_raid_damage_pct     = 0
        user.region_income_building_pct = 0
        user.region_trainer_discount    = 0

    @staticmethod
    def _bonus_values(cfg, is_owner: bool) -> dict:
        o = is_owner
        return {
            "region_income_pct":          cfg.owner_income_pct          if o else cfg.member_income_pct,
            "region_ticket_pct":          0,
            "region_power_pct":           0,
            "region_passive_income":      cfg.owner_passive_income      if o else cfg.member_passive_income,
            "region_war_genius":          cfg.owner_war_genius          if o else cfg.member_war_genius,
            "region_train_cd_pct":        cfg.owner_train_cd_pct        if o else cfg.member_train_cd_pct,
            "region_raid_cd_pct":         cfg.owner_raid_cd_pct         if o else cfg.member_raid_cd_pct,
            "region_fragment_pct":        cfg.owner_fragment_pct        if o else cfg.member_fragment_pct,
            "region_squad_power_pct":     cfg.owner_squad_power_pct     if o else cfg.member_squad_power_pct,
            "region_char_power_pct":      cfg.owner_char_power_pct      if o else cfg.member_char_power_pct,
            "region_ticket_overflow":     cfg.owner_ticket_overflow      if o else cfg.member_ticket_overflow,
            "region_double_ticket":       cfg.owner_double_ticket        if o else cfg.member_double_ticket,
            "region_raid_damage_pct":     cfg.owner_raid_damage_pct     if o else cfg.member_raid_damage_pct,
            "region_income_building_pct": cfg.owner_income_building_pct if o else cfg.member_income_building_pct,
            "region_trainer_discount":    cfg.owner_trainer_discount    if o else cfg.member_trainer_discount,
        }

    @staticmethod
    def _zero_values() -> dict:
        return {
            "region_income_pct": 0, "region_ticket_pct": 0, "region_power_pct": 0,
            "region_passive_income": 0, "region_war_genius": 0,
            "region_train_cd_pct": 0, "region_raid_cd_pct": 0, "region_fragment_pct": 0,
            "region_squad_power_pct": 0, "region_char_power_pct": 0,
            "region_ticket_overflow": False, "region_double_ticket": False,
            "region_raid_damage_pct": 0, "region_income_building_pct": 0,
            "region_trainer_discount": 0,
        }

    async def apply_region_bonuses_for_clan(
        self, session: AsyncSession, clan_id: int, region: "KoreanRegion"
    ) -> None:
        from app.models.user import User
        from app.data.regions import REGION_BY_SLUG
        cfg = REGION_BY_SLUG.get(region.slug)
        if not cfg:
            return
        members = await self.get_clan_members(session, clan_id)
        if not members:
            return
        # Bulk UPDATE: 1 query for owner, 1 for members (vs N individual UPDATEs)
        clan = await session.scalar(select(Clan).where(Clan.id == clan_id))
        owner_id = clan.owner_id if clan else None
        member_ids = [m.user_id for m in members if m.user_id != owner_id]
        if owner_id and any(m.user_id == owner_id for m in members):
            await session.execute(
                sa_update(User).where(User.id == owner_id)
                .values(**self._bonus_values(cfg, True))
            )
        if member_ids:
            await session.execute(
                sa_update(User).where(User.id.in_(member_ids))
                .values(**self._bonus_values(cfg, False))
            )
        await session.flush()

    async def apply_region_bonuses_for_user(
        self, session: AsyncSession, user: "User", clan_id: int
    ) -> None:
        from app.data.regions import REGION_BY_SLUG
        region = await self.get_clan_region(session, clan_id)
        if not region:
            self._zero_region_bonuses(user)
            return
        cfg = REGION_BY_SLUG.get(region.slug)
        if not cfg:
            self._zero_region_bonuses(user)
            return
        clan = await session.scalar(select(Clan).where(Clan.id == clan_id))
        is_owner = clan and clan.owner_id == user.id
        self._set_region_bonuses(user, cfg, is_owner)

    async def clear_region_bonuses_for_clan(
        self, session: AsyncSession, clan_id: int
    ) -> None:
        from app.models.user import User
        members = await self.get_clan_members(session, clan_id)
        if not members:
            return
        user_ids = [m.user_id for m in members]
        await session.execute(
            sa_update(User).where(User.id.in_(user_ids)).values(**self._zero_values())
        )
        await session.flush()

    async def clear_region_bonuses_for_user(self, user: "User") -> None:
        self._zero_region_bonuses(user)
