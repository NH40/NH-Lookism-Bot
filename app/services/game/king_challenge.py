"""GameKingChallengeService — вызов трона: король против короля своей страны (патч 1.3.1)."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.combat_service import fight_player
from app.services.cooldown_service import cooldown_service
from app.services.business_service import business_service
from app.services.game.base import GameBase
from app.services.game.utils import notify_pvp_attack
from app.utils.truce import is_truce_active
from app.config.game_balance import KING_CHALLENGE_CD_SECONDS


class GameKingChallengeService(GameBase):

    async def king_challenge_throne(
        self, session: AsyncSession, attacker: User, defender_id: int
    ) -> dict:
        if attacker.phase != "king":
            return {"ok": False, "reason": "Только для фазы Короля"}
        if is_truce_active(attacker):
            return {"ok": False, "reason": "Во время перемирия нельзя атаковать"}

        cd_key = cooldown_service.king_challenge_key(attacker.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"КД: {cooldown_service.format_ttl(ttl)}", "cd": ttl}

        from app.repositories.user_repo import user_repo
        defender = await user_repo.get_by_id(session, defender_id)
        if not defender or defender.phase != "king":
            return {"ok": False, "reason": "Противник не найден"}
        if defender.id == attacker.id:
            return {"ok": False, "reason": "Нельзя бросить вызов себе"}

        from app.data.cities import DEFAULT_COUNTRY
        if (defender.country or DEFAULT_COUNTRY) != (attacker.country or DEFAULT_COUNTRY):
            return {"ok": False, "reason": "Борьба за трон — только внутри своей страны"}
        if is_truce_active(defender):
            return {"ok": False, "reason": f"{defender.full_name} находится под перемирием"}

        result = await fight_player(session, attacker, defender)
        await cooldown_service.set_cooldown(cd_key, KING_CHALLENGE_CD_SECONDS)

        if result["win"]:
            old_suzerain_id = defender.suzerain_id
            if old_suzerain_id and old_suzerain_id != attacker.id:
                old_suzerain = await session.get(User, old_suzerain_id)
                if old_suzerain:
                    old_suzerain.vassal_count = max(0, old_suzerain.vassal_count - 1)
                    await business_service._recalc_income(session, old_suzerain)
            # Атакующий мог сам быть вассалом защитника — освобождаем его
            # ПЕРЕД тем, как защитник станет вассалом атакующего, иначе
            # получается взаимный цикл (A вассал B и B вассал A одновременно,
            # репро от тестера: "я вассал колумбины, колумбина мой вассал").
            if attacker.suzerain_id == defender.id:
                attacker.suzerain_id = None
                defender.vassal_count = max(0, defender.vassal_count - 1)
            if defender.suzerain_id != attacker.id:
                defender.suzerain_id = attacker.id
                attacker.vassal_count += 1
                await business_service._recalc_income(session, attacker)
            await business_service._recalc_income(session, defender)
            await self._check_emperor_eligibility(session, attacker)

        await notify_pvp_attack(
            attacker, defender, result["win"], "king_challenge",
            result["attacker_power"], result["defender_power"],
        )
        await session.flush()

        return {
            "ok": True, "win": result["win"],
            "is_crit": result["is_crit"],
            "attacker_power": result["attacker_power"],
            "defender_power": result["defender_power"],
            "defender_name": defender.full_name,
            "vassalized": result["win"],
        }
