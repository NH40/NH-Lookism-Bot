from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update as sa_update

from app.models.clan import Clan, ClanMember
from app.models.clan_region import (
    KoreanRegion,
    KoreanRegionWar,
    KoreanRegionWarParticipant,
    KoreanRegionActivity,
)
from app.models.user import User
from app.services.clan.base import ClanBaseService

from app.config.game_balance import (
    REGION_WAR_MAX_MEMBERS,
    REGION_WAR_MIN_SCORE,
    REGION_WAR_HOURS,
    REGION_SHIELD_HOURS,
    REGION_SHIELD_CD_HOURS,
    REGION_VS_REGION_CD_HOURS,
    REGION_VS_REGION_WIN_MULTIPLIER,
)

RANK_LABELS = {
    "owner": "👑 Владелец",
    "deputy": "🛡 Заместитель",
    "captain": "⚔️ Капитан",
    "member": "👤 Участник",
}

# Ранги, которые могут управлять войной (начать/отменить)
WAR_ALLOWED_RANKS = {"owner", "deputy"}


def _calc_personal_score(a: KoreanRegionActivity) -> int:
    return (
        min(a.train_count, 10) * 1
        + min(a.attack_gang_count, 5) * 2
        + min(a.attack_king_count, 5) * 3
        + min(a.attack_fist_count, 3) * 4
        + min(a.spend_count, 10) * 1
        + min(a.raid_count, 5) * 3
        + min(a.recruit_count, 10) * 1
        + min(a.auction_count, 5) * 2
        + min(a.duel_count, 5) * 3
        + min(a.market_count, 5) * 1
        + min(a.campaign_count, 3) * 4
        + min(a.boss_count, 5) * 3
        + min(a.quest_count, 5) * 2
        + min(a.bank_count, 5) * 1
    )


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
        """Активная война клана — 1 LEFT JOIN вместо 3 запросов."""
        return await session.scalar(
            select(KoreanRegionWar)
            .outerjoin(
                KoreanRegionWarParticipant,
                KoreanRegionWarParticipant.war_id == KoreanRegionWar.id,
            )
            .where(
                KoreanRegionWar.is_finished == False,
                or_(
                    KoreanRegionWar.initiator_clan_id == clan_id,
                    KoreanRegionWarParticipant.clan_id == clan_id,
                ),
            )
            .limit(1)
        )

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

        # Клан с регионом не может атаковать (макс 1 регион на клан)
        own_region = await self.get_clan_region(session, clan.id)
        if own_region:
            return {"ok": False, "reason": "У вашего клана уже есть регион. Клан может владеть только одним регионом."}

        if region.owner_clan_id == clan.id:
            return {"ok": False, "reason": "Ваш клан уже владеет этим регионом"}

        member_count = await self.get_clan_member_count(session, clan.id)
        if member_count > REGION_WAR_MAX_MEMBERS:
            return {
                "ok": False,
                "reason": f"Клан не может участвовать при более {REGION_WAR_MAX_MEMBERS} участниках",
            }

        # Клан уже в войне
        existing = await self.get_active_war_for_clan(session, clan.id)
        if existing:
            return {"ok": False, "reason": "Ваш клан уже участвует в войне за регион"}

        # Есть активная война → присоединиться
        active_war = await self.get_active_war_for_region(session, region.id)
        if active_war:
            return await self.join_region_war(session, clan, active_war, requester_id)

        now = datetime.now(timezone.utc)

        # Проверяем щит на регионе
        if region.shield_until and region.shield_until > now:
            remaining = int((region.shield_until - now).total_seconds())
            h, m = divmod(remaining // 60, 60)
            return {"ok": False, "reason": f"Регион защищён щитом ещё {h}ч {m}м"}

        war = KoreanRegionWar(
            region_id=region.id,
            initiator_clan_id=clan.id,
            war_type="capture",
            ends_at=now + timedelta(hours=REGION_WAR_HOURS),
        )
        session.add(war)
        await session.flush()

        session.add(KoreanRegionWarParticipant(war_id=war.id, clan_id=clan.id, score=0))

        # Если регион уже занят → авто-добавляем клан-владельца как защитника
        defender_clan_id = None
        if region.owner_clan_id and region.owner_clan_id != clan.id:
            defender_clan_id = region.owner_clan_id
            session.add(KoreanRegionWarParticipant(war_id=war.id, clan_id=defender_clan_id, score=0))

        await session.flush()

        return {
            "ok": True,
            "war_id": war.id,
            "ends_at": war.ends_at,
            "joined": False,
            "defender_clan_id": defender_clan_id,
        }

    async def join_region_war(
        self, session: AsyncSession, clan: Clan, war: KoreanRegionWar, requester_id: int
    ) -> dict:
        rank = await self.get_member_rank(session, clan.id, requester_id)
        if rank not in WAR_ALLOWED_RANKS:
            return {"ok": False, "reason": "Только владелец или заместитель может присоединиться к войне"}

        member_count = await self.get_clan_member_count(session, clan.id)
        if member_count > REGION_WAR_MAX_MEMBERS:
            return {
                "ok": False,
                "reason": f"Клан не может участвовать при более {REGION_WAR_MAX_MEMBERS} участниках",
            }

        own_region = await self.get_clan_region(session, clan.id)
        if own_region:
            return {"ok": False, "reason": "Клан с регионом не может участвовать в захвате."}

        existing = await self.get_active_war_for_clan(session, clan.id)
        if existing:
            return {"ok": False, "reason": "Клан уже участвует в другой войне за регион"}

        already = await session.scalar(
            select(KoreanRegionWarParticipant).where(
                KoreanRegionWarParticipant.war_id == war.id,
                KoreanRegionWarParticipant.clan_id == clan.id,
            )
        )
        if already:
            return {"ok": False, "reason": "Клан уже участвует в этой войне"}

        session.add(KoreanRegionWarParticipant(war_id=war.id, clan_id=clan.id, score=0))
        await session.flush()

        return {"ok": True, "war_id": war.id, "ends_at": war.ends_at, "joined": True}

    # ── Война регион-vs-регион (за ОА) ────────────────────────────────────────

    async def start_region_vs_region_war(
        self, session: AsyncSession, attacker_clan: Clan, defender_region: KoreanRegion, requester_id: int
    ) -> dict:
        """Клан с регионом объявляет войну другому клану с регионом — за ОА, без смены владельца."""
        rank = await self.get_member_rank(session, attacker_clan.id, requester_id)
        if rank not in WAR_ALLOWED_RANKS:
            return {"ok": False, "reason": "Только владелец или заместитель может объявить войну"}

        attacker_region = await self.get_clan_region(session, attacker_clan.id)
        if not attacker_region:
            return {"ok": False, "reason": "У вашего клана нет региона"}

        if not defender_region.owner_clan_id:
            return {"ok": False, "reason": "У этого региона нет владельца"}

        if defender_region.owner_clan_id == attacker_clan.id:
            return {"ok": False, "reason": "Нельзя объявить войну самому себе"}

        now = datetime.now(timezone.utc)

        if attacker_clan.region_war_cd_until and attacker_clan.region_war_cd_until > now:
            remaining = int((attacker_clan.region_war_cd_until - now).total_seconds())
            h, m = divmod(remaining // 60, 60)
            return {"ok": False, "reason": f"Ваш клан в КД ещё {h}ч {m}м"}

        defender_clan = await session.scalar(select(Clan).where(Clan.id == defender_region.owner_clan_id))
        if not defender_clan:
            return {"ok": False, "reason": "Клан-владелец не найден"}

        if defender_clan.region_war_cd_until and defender_clan.region_war_cd_until > now:
            remaining = int((defender_clan.region_war_cd_until - now).total_seconds())
            h, m = divmod(remaining // 60, 60)
            return {"ok": False, "reason": f"Клан противника в КД ещё {h}ч {m}м"}

        if defender_region.shield_until and defender_region.shield_until > now:
            remaining = int((defender_region.shield_until - now).total_seconds())
            h, m = divmod(remaining // 60, 60)
            return {"ok": False, "reason": f"Регион противника защищён щитом ещё {h}ч {m}м"}

        for cid in (attacker_clan.id, defender_clan.id):
            existing = await self.get_active_war_for_clan(session, cid)
            if existing:
                whose = "Ваш клан" if cid == attacker_clan.id else "Клан противника"
                return {"ok": False, "reason": f"{whose} уже участвует в войне за регион"}

        from app.config.game_balance import REGION_VS_REGION_WAR_HOURS
        war = KoreanRegionWar(
            region_id=defender_region.id,
            initiator_clan_id=attacker_clan.id,
            war_type="region_vs_region",
            ends_at=now + timedelta(hours=REGION_VS_REGION_WAR_HOURS),
        )
        session.add(war)
        await session.flush()

        for cid in (attacker_clan.id, defender_clan.id):
            session.add(KoreanRegionWarParticipant(war_id=war.id, clan_id=cid, score=0))
        await session.flush()

        return {
            "ok": True,
            "war_id": war.id,
            "ends_at": war.ends_at,
            "defender_clan_id": defender_clan.id,
            "defender_clan_name": defender_clan.name,
        }

    # ── Щит региона ───────────────────────────────────────────────────────────

    async def activate_region_shield(
        self, session: AsyncSession, clan: Clan, region: KoreanRegion
    ) -> dict:
        """Активирует щит на регионе клана (12ч защиты, затем 10ч КД)."""
        if region.owner_clan_id != clan.id:
            return {"ok": False, "reason": "Ваш клан не владеет этим регионом"}

        now = datetime.now(timezone.utc)

        if region.shield_until and region.shield_until > now:
            remaining = int((region.shield_until - now).total_seconds())
            h, m = divmod(remaining // 60, 60)
            return {"ok": False, "reason": f"Щит уже активен ещё {h}ч {m}м"}

        if region.shield_cd_until and region.shield_cd_until > now:
            remaining = int((region.shield_cd_until - now).total_seconds())
            h, m = divmod(remaining // 60, 60)
            return {"ok": False, "reason": f"Щит на перезарядке ещё {h}ч {m}м"}

        shield_until = now + timedelta(hours=REGION_SHIELD_HOURS)
        region.shield_until = shield_until
        region.shield_cd_until = shield_until + timedelta(hours=REGION_SHIELD_CD_HOURS)
        await session.flush()

        return {"ok": True, "shield_until": shield_until}

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

        # ОА зарабатываются в реальном времени — те же очки что и военный счёт
        await session.execute(
            sa_update(User).where(User.id == user_id)
            .values(activity_points=User.activity_points + pts)
        )

        # Добавляем очки участнику клана
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
        if war.war_type == "region_vs_region":
            return await self._resolve_rvr_war(session, war)
        return await self._resolve_capture_war(session, war)

    async def _resolve_rvr_war(self, session: AsyncSession, war: KoreanRegionWar) -> dict:
        """RvR: победитель ×1.5 ОА, проигравший ×1. Регион не переходит."""
        participants = await self.get_war_participants(session, war.id)
        war.is_finished = True

        if not participants:
            await session.flush()
            return {"ok": False, "reason": "no_participants"}

        best = max(participants, key=lambda p: p.score)
        war.winner_clan_id = best.clan_id
        now = datetime.now(timezone.utc)
        cd_until = now + timedelta(hours=REGION_VS_REGION_CD_HOURS)

        for p in participants:
            clan = await session.scalar(select(Clan).where(Clan.id == p.clan_id))
            if not clan:
                continue
            is_winner = p.clan_id == best.clan_id
            ap = int(p.score * REGION_VS_REGION_WIN_MULTIPLIER) if is_winner else p.score
            clan.treasury_ap = (clan.treasury_ap or 0) + ap
            clan.region_war_cd_until = cd_until

        region = await self.get_region_by_id(session, war.region_id)
        await session.flush()
        return {
            "ok": True,
            "war_type": "region_vs_region",
            "winner_clan_id": best.clan_id,
            "region_id": war.region_id,
            "region_name": region.name if region else "?",
            "region_emoji": region.emoji if region else "🗺",
            "winner_score": best.score,
            "prev_owner_clan_id": None,
            "region_transferred": False,
        }

    async def _resolve_capture_war(self, session: AsyncSession, war: KoreanRegionWar) -> dict:
        """Завершает войну за регион.

        Если регион был занят → был защитник. Победитель получает регион и ×1.5 ОА,
        проигравший — свои очки. Оба клана получают 4ч КД.
        """
        region = await self.get_region_by_id(session, war.region_id)
        if not region:
            war.is_finished = True
            await session.flush()
            return {"ok": False}

        participants = await self.get_war_participants(session, war.id)
        war.is_finished = True

        if not participants:
            await session.flush()
            return {"ok": False, "reason": "no_participants"}

        best = max(participants, key=lambda p: p.score)
        now = datetime.now(timezone.utc)
        prev_owner_clan_id = region.owner_clan_id
        was_contested = prev_owner_clan_id is not None

        if best.score < REGION_WAR_MIN_SCORE:
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
                "region_emoji": region.emoji,
                "best_score": best.score,
                "min_score": REGION_WAR_MIN_SCORE,
            }

        war.winner_clan_id = best.clan_id
        cd_until = now + timedelta(hours=REGION_VS_REGION_CD_HOURS) if was_contested else None

        # ОА в казну + КД для всех участников
        for p in participants:
            p_clan = await session.scalar(select(Clan).where(Clan.id == p.clan_id))
            if not p_clan:
                continue
            is_winner = p.clan_id == best.clan_id
            if was_contested:
                ap_earned = int(p.score * REGION_VS_REGION_WIN_MULTIPLIER) if is_winner else p.score
                p_clan.region_war_cd_until = cd_until
            else:
                ap_earned = p.score
            p_clan.treasury_ap = (p_clan.treasury_ap or 0) + ap_earned

        # Передача региона
        if prev_owner_clan_id and prev_owner_clan_id != best.clan_id:
            await self.clear_region_bonuses_for_clan(session, prev_owner_clan_id)
        region.owner_clan_id = best.clan_id
        await session.flush()
        await self.apply_region_bonuses_for_clan(session, best.clan_id, region)

        return {
            "ok": True,
            "winner_clan_id": best.clan_id,
            "prev_owner_clan_id": prev_owner_clan_id,
            "region_transferred": was_contested and prev_owner_clan_id != best.clan_id,
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
        from app.data.regions import REGION_BY_SLUG
        cfg = REGION_BY_SLUG.get(region.slug)
        if not cfg:
            return
        # Субзапрос: не грузим участников в память
        count = await self.get_clan_member_count(session, clan_id)
        if not count:
            return
        clan = await session.scalar(select(Clan).where(Clan.id == clan_id))
        owner_id = clan.owner_id if clan else None
        # 1 запрос для владельца, 1 для остальных
        if owner_id:
            await session.execute(
                sa_update(User).where(User.id == owner_id)
                .values(**self._bonus_values(cfg, True))
            )
        member_subq = (
            select(ClanMember.user_id)
            .where(ClanMember.clan_id == clan_id, ClanMember.user_id != owner_id)
        )
        await session.execute(
            sa_update(User).where(User.id.in_(member_subq))
            .values(**self._bonus_values(cfg, False))
        )
        await session.flush()
        await self.recalc_clan_region_income(session, clan_id, has_region=True)

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
        # Субзапрос — не грузим участников в память
        subq = select(ClanMember.user_id).where(ClanMember.clan_id == clan_id)
        await session.execute(
            sa_update(User).where(User.id.in_(subq))
            .values(**self._zero_values(), clan_region_income=0)
        )
        await session.flush()

    async def clear_region_bonuses_for_user(self, user: "User") -> None:
        self._zero_region_bonuses(user)
