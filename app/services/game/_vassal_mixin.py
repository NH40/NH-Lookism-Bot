"""VassalMixin — битва за трон города, вассалитет, городской налог, завоевание страны (патч 1.3.1)."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update as sql_update

from app.models.user import User
from app.models.city import City, District


class VassalMixin:

    async def _resolve_city_title_battle(
        self, session: AsyncSession, challenger: User, reigning_king: User, city: City
    ) -> dict:
        """challenger только что захватил 100% районов города, которым уже
        владеет другой король. Победитель занимает трон города (владение
        районами при этом не трогается — оно уже определено предыдущими
        боями кражи районов). Обе стороны несут потери статистов/карточек
        (apply_battle_casualties) — проигравший больше НЕ уничтожается
        автоматически целиком; полное разжалование из Короля наступает
        только естественно, если после боя у него не осталось ни одного
        города с районами (как и при обычной потере районов по одному)."""
        from app.services.combat_service import fight_player
        from app.services.game.utils import apply_battle_casualties
        result = await fight_player(session, challenger, reigning_king)
        winner, loser = (challenger, reigning_king) if result["win"] else (reigning_king, challenger)

        # challenger — всегда "атакующий" по роли (это он полез отбирать
        # трон), reigning_king — "защитник", независимо от того, кто в
        # итоге выиграл сам бой.
        casualties = await apply_battle_casualties(session, challenger, reigning_king, result["win"])

        city.owner_id = winner.id

        from app.repositories.city_repo import city_repo
        await city_repo.sync_captured_districts(session, city.id)
        await self._recalc_city_tax_for_city_residents(session, city.id)

        loser_cities = await self._count_my_king_cities(session, loser.id)
        loser_destroyed = False
        if loser_cities == 0:
            await self._destroy_king(session, loser)
            loser_destroyed = True
        else:
            loser.king_cities_count = loser_cities

        # Император проверяется только для инициатора боя (challenger).
        # Если трон отстоял защищавшийся reigning_king, это не должно молча
        # производить его в Императоры без его действия — иначе чужая атака,
        # которую вы просто отбили, может внезапно завершить завоевание
        # страны и мгновенно освободить все ваши королевские районы
        # (баг "стал императором без своей воли").
        if winner.id == challenger.id:
            await self._check_emperor_eligibility(session, winner)

        return {
            "battle": True, "fight": result, "winner_id": winner.id, "loser_id": loser.id,
            "casualties": casualties, "loser_destroyed": loser_destroyed,
        }

    async def _check_and_resolve_city_ownership(
        self, session: AsyncSession, user: User, city: City
    ) -> dict | None:
        """Вызывается после того, как user получил район(ы) в городе. Если user
        теперь владеет 100% районов города:
          - город ничей → занимает трон, налог соседей пересчитан
          - город чужой → битва за трон (возвращает результат _resolve_city_title_battle)
          - город уже его → ничего не делает
        Возвращает None, если трон не оспаривался (или user уже на троне)."""
        my_in_city = await self._get_my_districts_in_city(session, user.id, city.id)
        if my_in_city < city.total_districts:
            return None
        if not city.owner_id:
            city.owner_id = user.id
            await self._recalc_city_tax_for_city_residents(session, city.id)
            return None
        if city.owner_id == user.id:
            return None

        from app.repositories.user_repo import user_repo
        old_king = await user_repo.get_by_id(session, city.owner_id)
        if not old_king:
            city.owner_id = user.id
            await self._recalc_city_tax_for_city_residents(session, city.id)
            return None
        return await self._resolve_city_title_battle(session, user, old_king, city)

    async def _release_vassals_of(self, session: AsyncSession, suzerain_id: int) -> None:
        """Снимает вассалитет со всех вассалов уничтоженного/сброшенного короля."""
        await session.execute(
            sql_update(User).where(User.suzerain_id == suzerain_id).values(suzerain_id=None)
        )
        await session.execute(
            sql_update(User).where(User.id == suzerain_id).values(vassal_count=0)
        )
        await session.flush()

    async def _recalc_city_tax(self, session: AsyncSession, user: User) -> None:
        """Считает долю районов пользователя в чужих городах-с-королём,
        кэширует city_tax_percent/city_tax_recipient_id. Вызывается из
        business_service._recalc_income — покрывает все существующие хуки захвата."""
        from app.config.game_balance import CITY_TAX_PERCENT

        rows = (await session.execute(
            select(District.city_id, func.count(District.id).label("cnt"))
            .where(District.owner_id == user.id, District.is_captured == True)
            .group_by(District.city_id)
        )).all()
        if not rows:
            user.city_tax_percent = 0
            user.city_tax_recipient_id = None
            return

        city_ids = [r.city_id for r in rows]
        owners = dict((await session.execute(
            select(City.id, City.owner_id).where(City.id.in_(city_ids))
        )).all())

        total = sum(r.cnt for r in rows)
        taxed_by_owner: dict[int, int] = {}
        for r in rows:
            owner = owners.get(r.city_id)
            if owner and owner != user.id:
                taxed_by_owner[owner] = taxed_by_owner.get(owner, 0) + r.cnt

        if not taxed_by_owner:
            user.city_tax_percent = 0
            user.city_tax_recipient_id = None
            return

        taxed_total = sum(taxed_by_owner.values())
        user.city_tax_recipient_id = max(taxed_by_owner.items(), key=lambda kv: kv[1])[0]
        user.city_tax_percent = round(CITY_TAX_PERCENT * taxed_total / total)

    async def _recalc_city_tax_for_city_residents(self, session: AsyncSession, city_id: int) -> None:
        """При смене владельца города пересчитывает налог для всех текущих
        резидентов (ограничено total_districts<=64 — не hot path)."""
        owner_ids = (await session.execute(
            select(District.owner_id).where(
                District.city_id == city_id,
                District.is_captured == True,
                District.owner_id != None,
            ).distinct()
        )).scalars().all()
        for uid in owner_ids:
            resident = await session.get(User, uid)
            if resident:
                await self._recalc_city_tax(session, resident)
        await session.flush()

    async def _count_ruled_cities(self, session: AsyncSession, user_id: int) -> int:
        return await session.scalar(
            select(func.count(City.id)).where(City.owner_id == user_id, City.phase == "gang")
        ) or 0

    async def _check_emperor_eligibility(self, session: AsyncSession, king: User) -> dict | None:
        """Король + его вассалы владеют ВСЕМИ gang-городами своей страны → Император."""
        if king.phase != "king":
            return None
        from app.data.cities import DEFAULT_COUNTRY
        country = king.country or DEFAULT_COUNTRY

        total_country_cities = await session.scalar(
            select(func.count(City.id)).where(City.country == country, City.phase == "gang")
        ) or 0
        if total_country_cities == 0:
            return None

        own = await self._count_ruled_cities(session, king.id)
        vassal_ids = (await session.execute(
            select(User.id).where(User.suzerain_id == king.id)
        )).scalars().all()
        vassal_cities = 0
        if vassal_ids:
            vassal_cities = await session.scalar(
                select(func.count(City.id)).where(
                    City.owner_id.in_(vassal_ids), City.phase == "gang"
                )
            ) or 0

        if own + vassal_cities >= total_country_cities:
            return await self._promote_to_emperor(session, king)
        return None
