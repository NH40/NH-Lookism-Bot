"""GameEmperorService — PvP между Императорами: победитель забирает 30%
статистов, карточек и денег проигравшего, плюс 1-3 случайных города
(патч 1.3.1, заменяет собой убранную фазу Кулака)."""
import random
from sqlalchemy import select, delete, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.city import City, District
from app.models.squad_member import SquadMember
from app.models.character import UserCharacter
from app.models.card_deck import UserDeck
from app.services.combat_service import fight_player
from app.services.cooldown_service import cooldown_service
from app.services.business_service import business_service
from app.services.game.base import GameBase
from app.services.game.utils import notify_pvp_attack, notify_country_city_loss
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
        stolen_squad = 0
        stolen_cards = 0
        captured_city_names: list[str] = []

        if result["win"]:
            pct = EMPEROR_PVP_STEAL_PERCENT

            # ── 30% статистов — построчно (SquadMember: составной PK) ──────
            squad_rows = (await session.execute(
                select(SquadMember).where(SquadMember.user_id == defender.id)
            )).scalars().all()
            for row in squad_rows:
                take = int(row.count * pct / 100)
                if take <= 0:
                    continue
                stolen_squad += take
                row.count -= take
                mine = await session.get(SquadMember, (attacker.id, row.rank, row.stars, row.base_power))
                if mine:
                    mine.count += take
                else:
                    session.add(SquadMember(
                        user_id=attacker.id, rank=row.rank, stars=row.stars,
                        base_power=row.base_power, count=take,
                    ))
                if row.count <= 0:
                    await session.delete(row)

            # ── 30% карточек — случайные экземпляры (не проценты от каждой) ─
            char_ids = (await session.execute(
                select(UserCharacter.id).where(UserCharacter.user_id == defender.id)
            )).scalars().all()
            take_n = int(len(char_ids) * pct / 100)
            if take_n > 0:
                stolen_ids = random.sample(char_ids, take_n)
                stolen_cards = len(stolen_ids)
                # Слоты колоды проигравшего, ссылающиеся именно на украденные карты
                await session.execute(
                    delete(UserDeck).where(
                        UserDeck.user_id == defender.id,
                        UserDeck.char_id.in_(stolen_ids),
                    )
                )
                await session.execute(
                    sql_update(UserCharacter).where(UserCharacter.id.in_(stolen_ids))
                    .values(user_id=attacker.id)
                )

            # ── 30% монет ────────────────────────────────────────────────────
            stolen_coins = int(defender.nh_coins * pct / 100)
            attacker.nh_coins += stolen_coins
            defender.nh_coins -= stolen_coins

            from app.repositories.squad_repo import squad_repo
            await squad_repo.update_user_combat_power(session, attacker)
            await squad_repo.update_user_combat_power(session, defender)
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
                await business_service._recalc_income(session, attacker)
                await business_service._recalc_income(session, defender)

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
            "captured_cities": captured_city_names,
        }
