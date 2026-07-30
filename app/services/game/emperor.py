"""GameEmperorService — PvP между Императорами: атакующий всегда теряет 100%
от статистов/карточек защитника (не больше своего запаса), защитник —
дополнительно 60% своих, если проиграл (apply_battle_casualties, патч 1.3.1
v3 — раньше терял только проигравший), а победитель дополнительно забирает
30% денег проигравшего и 1-3 случайных города (заменяет собой убранную фазу
Кулака)."""
import random
from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.city import City, District
from app.services.combat_service import fight_player
from app.services.cooldown_service import cooldown_service
from app.services.business_service import business_service
from app.services.game.base import GameBase
from app.services.game.utils import notify_pvp_attack, notify_country_city_loss, apply_battle_casualties
from app.utils.truce import is_truce_active
from app.config.game_balance import EMPEROR_PVP_CD_SECONDS, EMPEROR_PVP_STEAL_PERCENT


class GameEmperorService(GameBase):

    async def emperor_pvp_attack(
        self, session: AsyncSession, attacker: User, defender_id: int
    ) -> dict:
        if attacker.phase != "emperor":
            return {"ok": False, "reason": "Только для фазы Императора"}
        if is_truce_active(attacker):
            return {"ok": False, "reason": "Во время перемирия нельзя атаковать"}

        cd_key = cooldown_service.emperor_pvp_key(attacker.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"КД: {cooldown_service.format_ttl(ttl)}", "cd": ttl}

        from app.repositories.user_repo import user_repo
        defender = await user_repo.get_by_id(session, defender_id)
        if not defender or defender.phase != "emperor":
            return {"ok": False, "reason": "Противник не найден"}
        if defender.id == attacker.id:
            return {"ok": False, "reason": "Нельзя атаковать себя"}
        if is_truce_active(defender):
            return {"ok": False, "reason": f"{defender.full_name} находится под перемирием"}

        result = await fight_player(session, attacker, defender)
        stolen_coins = 0
        captured_city_names: list[str] = []

        # Атакующий всегда теряет 100% от количества защитника (не больше
        # своего), защитник — доп. 60% своих, если проиграл.
        casualties = await apply_battle_casualties(session, attacker, defender, result["win"])
        stolen_squad = casualties["defender_statists_lost"]
        stolen_cards = casualties["defender_cards_lost"]

        if result["win"]:
            pct = EMPEROR_PVP_STEAL_PERCENT

            # ── 30% монет ────────────────────────────────────────────────────
            stolen_coins = int(defender.nh_coins * pct / 100)
            attacker.nh_coins += stolen_coins
            defender.nh_coins -= stolen_coins

            attacker.total_wins += 1

            # ── 1-3 случайных города проигравшего переходят победителю ──────
            # (районы внутри них уже "боты" — см. _promote_to_emperor; тут
            # переходит именно трон City.owner_id, а с ним и городской налог
            # с текущих жителей этих городов).
            defender_cities = (await session.execute(
                select(City).where(City.owner_id == defender.id, City.phase == "gang")
            )).scalars().all()
            if defender_cities:
                n = min(random.randint(1, 3), len(defender_cities))
                taken_cities = random.sample(defender_cities, n)
                taken_city_ids = [c.id for c in taken_cities]
                for city in taken_cities:
                    city.owner_id = attacker.id
                    captured_city_names.append(city.name)
                # Историческая привязка дохода (income_owner_id) с районов
                # этих городов тоже переходит победителю вместе с троном —
                # иначе Император-победитель забрал бы город, но доход с его
                # районов продолжал бы капать проигравшему.
                await session.execute(
                    sql_update(District).where(
                        District.city_id.in_(taken_city_ids),
                        District.income_owner_id == defender.id,
                    ).values(income_owner_id=attacker.id)
                )
                await session.flush()
                for city in taken_cities:
                    await self._recalc_city_tax_for_city_residents(session, city.id)
                await business_service._recalc_income(session, attacker, recalc_tax=True)
                await business_service._recalc_income(session, defender, recalc_tax=True)

        await notify_pvp_attack(attacker, defender, result["win"], "emperor_pvp")
        if result["win"] and captured_city_names:
            country = defender.country or "unknown"
            await notify_country_city_loss(session, country, defender, attacker, captured_city_names)
        await cooldown_service.set_cooldown(cd_key, EMPEROR_PVP_CD_SECONDS)
        await session.flush()

        return {
            "ok": True, "win": result["win"],
            "is_crit": result["is_crit"],
            "attacker_power": result["attacker_power"],
            "defender_power": result["defender_power"],
            "defender_name": defender.full_name,
            "stolen_coins": stolen_coins,
            "stolen_squad": stolen_squad,
            "stolen_cards": stolen_cards,
            "casualties": casualties,
            "captured_cities": captured_city_names,
        }
