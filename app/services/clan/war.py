import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.clan import Clan, ClanMember, ClanWar
from app.services.clan.base import ClanBaseService
from app.config.game_balance import (
    CLAN_WAR_WINNER_MULTIPLIER,
    CLAN_WAR_LOSER_MULTIPLIER,
    CLAN_WAR_WINNER_BASE,
    CLAN_WAR_LOSER_BASE,
    CLAN_WAR_MAX_REWARD,
    CLAN_WAR_POWER_HOURS,
    CLAN_WAR_TREASURY_HOURS,
)


class ClanWarService(ClanBaseService):

    async def start_war(self, session: AsyncSession, attacker_clan: Clan, defender_clan: Clan, war_type: str, owner: User) -> dict:
        if attacker_clan.owner_id != owner.id:
            return {"ok": False, "reason": "Только владелец может начать войну"}
        if attacker_clan.id == defender_clan.id:
            return {"ok": False, "reason": "Нельзя воевать с собой"}
        active = await session.scalar(
            select(ClanWar).where(
                ClanWar.is_finished == False,
                (ClanWar.clan1_id == attacker_clan.id) | (ClanWar.clan2_id == attacker_clan.id)
            )
        )
        if active:
            return {"ok": False, "reason": "Клан уже участвует в войне"}
        hours = CLAN_WAR_POWER_HOURS if war_type == "power" else CLAN_WAR_TREASURY_HOURS
        now = datetime.now(timezone.utc)
        start1 = attacker_clan.combat_power if war_type == "power" else attacker_clan.treasury
        start2 = defender_clan.combat_power if war_type == "power" else defender_clan.treasury
        war = ClanWar(
            clan1_id=attacker_clan.id, clan2_id=defender_clan.id,
            war_type=war_type, clan1_start=start1, clan2_start=start2,
            ends_at=now + timedelta(hours=hours),
        )
        session.add(war)
        await session.flush()
        return {"ok": True, "war_id": war.id, "ends_at": war.ends_at}

    async def finish_expired_wars(self, session: AsyncSession) -> list[dict]:
        """Завершает просроченные войны и выдаёт награды."""
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(ClanWar).where(ClanWar.is_finished == False, ClanWar.ends_at <= now)
        )
        wars = result.scalars().all()
        finished = []
        for war in wars:
            outcome = await self._finish_war(session, war)
            finished.append(outcome)
        return finished

    async def _finish_war(self, session: AsyncSession, war: ClanWar) -> dict:
        clan1 = await session.scalar(select(Clan).where(Clan.id == war.clan1_id))
        clan2 = await session.scalar(select(Clan).where(Clan.id == war.clan2_id))
        if not clan1 or not clan2:
            war.is_finished = True
            await session.flush()
            return {"ok": False}

        if war.war_type == "power":
            gain1 = clan1.combat_power - war.clan1_start
            gain2 = clan2.combat_power - war.clan2_start
        else:
            gain1 = clan1.treasury - war.clan1_start
            gain2 = clan2.treasury - war.clan2_start

        if gain1 >= gain2:
            winner, loser = clan1, clan2
            winner_gain, loser_gain = gain1, gain2
        else:
            winner, loser = clan2, clan1
            winner_gain, loser_gain = gain2, gain1

        # Capture primitives before flush — async session expires ORM objects on flush
        winner_id = winner.id
        loser_id = loser.id
        war_type = war.war_type

        # Награды в казну (не более CLAN_WAR_MAX_REWARD каждой стороне)
        winner_reward = min(
            int(abs(winner_gain) * CLAN_WAR_WINNER_MULTIPLIER) + CLAN_WAR_WINNER_BASE,
            CLAN_WAR_MAX_REWARD,
        )
        loser_reward = min(
            int(abs(loser_gain) * CLAN_WAR_LOSER_MULTIPLIER) + CLAN_WAR_LOSER_BASE,
            CLAN_WAR_MAX_REWARD,
        )
        winner.treasury += winner_reward
        loser.treasury += loser_reward

        war.is_finished = True
        war.winner_clan_id = winner_id
        await session.flush()

        return {
            "ok": True,
            "winner_id": winner_id,
            "loser_id": loser_id,
            "winner_reward": winner_reward,
            "loser_reward": loser_reward,
            "war_type": war_type,
        }