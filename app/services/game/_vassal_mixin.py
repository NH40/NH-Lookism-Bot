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
        if not old_king or old_king.phase != "king":
            # Владелец трона не найден либо уже не в фазе Короля (ушёл в
            # Императоры — трон остаётся за ним навсегда ради налога, см.
            # _promote_to_emperor, но сам он в фазе king больше не участвует
            # и не может "защищаться"). Заставлять претендента драться с
            # ЖИВОЙ (вечно растущей) мощью ушедшего Императора несправедливо
            # и блокирует завоевание страны намертво — тот же класс бага,
            # что и в _promote_to_king (баг 13/16), только здесь для
            # king-фазных атак вместо gang-фазных. Трон переходит без боя.
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

    async def _count_ruled_cities(
        self, session: AsyncSession, user_id: int, country: str | None = None
    ) -> int:
        conditions = [City.owner_id == user_id, City.phase == "gang"]
        if country is not None:
            conditions.append(City.country == country)
        return await session.scalar(select(func.count(City.id)).where(*conditions)) or 0

    async def _is_emperor_eligible(self, session: AsyncSession, king: User) -> bool:
        """Король + его вассалы владеют ВСЕМИ gang-городами своей страны."""
        if king.phase != "king":
            return False
        from app.data.cities import DEFAULT_COUNTRY
        country = king.country or DEFAULT_COUNTRY

        total_country_cities = await session.scalar(
            select(func.count(City.id)).where(City.country == country, City.phase == "gang")
        ) or 0
        if total_country_cities == 0:
            return False

        # Считаем города СТРОГО в текущей стране игрока. City.owner_id
        # никогда не очищается при пробуждении (Императоры навсегда сохраняют
        # налог со старых городов, см. prestige_service._reset_progress) —
        # без фильтра по стране трон-города из ПРЕДЫДУЩЕЙ жизни (другая
        # страна) молча засчитывались бы в захват НОВОЙ страны, позволяя
        # стать Императором почти сразу с 0-1 городом (баг 4: "можно стать
        # Императором вообще без городов").
        own = await self._count_ruled_cities(session, king.id, country=country)
        vassal_ids = (await session.execute(
            select(User.id).where(User.suzerain_id == king.id)
        )).scalars().all()
        vassal_cities = 0
        if vassal_ids:
            vassal_cities = await session.scalar(
                select(func.count(City.id)).where(
                    City.owner_id.in_(vassal_ids), City.country == country, City.phase == "gang"
                )
            ) or 0

        return own + vassal_cities >= total_country_cities

    async def _check_emperor_eligibility(self, session: AsyncSession, king: User) -> dict | None:
        """Если Король выполнил условие захвата всей страны (сам + вассалы
        владеют всеми gang-городами) — либо становится Императором СРАЗУ
        (страна ещё ни разу не была завоёвана, некого свергать), либо, если
        в стране уже есть действующий Император, ничего не происходит
        автоматически: Король получает доступ к явному вызову "Бросить вызов
        Императору" (см. challenge_emperor) — раньше конкурента просто молча
        промотировало мимо уже коронованного Императора, что и не давало
        игроку способа реально сразиться за трон страны."""
        if not await self._is_emperor_eligible(session, king):
            return None
        from app.data.cities import DEFAULT_COUNTRY
        country = king.country or DEFAULT_COUNTRY

        existing_emperor = await session.scalar(
            select(func.count(User.id)).where(User.phase == "emperor", User.country == country)
        ) or 0
        if existing_emperor > 0:
            return None
        return await self._promote_to_emperor(session, king)

    async def get_kings_conquest_progress(
        self, session: AsyncSession, country: str
    ) -> list[dict]:
        """Для экрана Императора: список Королей его страны с прогрессом
        захвата (свои + вассальные города / всего городов страны) и их
        боевой мощью — Император должен видеть, кто и насколько близок к
        вызову за его трон (см. challenge_emperor)."""
        total_country_cities = await session.scalar(
            select(func.count(City.id)).where(City.country == country, City.phase == "gang")
        ) or 0

        kings = (await session.execute(
            select(User).where(User.phase == "king", User.country == country)
        )).scalars().all()

        result = []
        for king in kings:
            own = await self._count_ruled_cities(session, king.id, country=country)
            vassal_ids = (await session.execute(
                select(User.id).where(User.suzerain_id == king.id)
            )).scalars().all()
            vassal_cities = 0
            if vassal_ids:
                vassal_cities = await session.scalar(
                    select(func.count(City.id)).where(
                        City.owner_id.in_(vassal_ids), City.country == country, City.phase == "gang"
                    )
                ) or 0
            result.append({
                "id": king.id, "name": king.full_name, "combat_power": king.combat_power,
                "cities": own + vassal_cities, "total_cities": total_country_cities,
            })
        result.sort(key=lambda r: r["cities"], reverse=True)
        return result

    async def _demote_to_gang(self, session: AsyncSession, user: User) -> None:
        """Полное поражение в серии вызовов за трон Империи (в любую сторону,
        3 победы подряд соперника) — теряет ВСЕ города/трон, откатывается на
        этап Банды с нуля (заново выбирает страну и город). НЕ трогает
        статистов/карточки/монеты/навыки — в отличие от _destroy_king это НЕ
        полный сброс прогресса, только владения и фаза."""
        await session.execute(
            sql_update(City).where(City.owner_id == user.id).values(owner_id=None)
        )
        await self._release_vassals_of(session, user.id)
        user.phase = "gang"
        user.country = None
        user.sector = None
        user.gang_city_id = None
        user.king_cities_count = 0
        user.suzerain_id = None
        user.city_tax_percent = 0
        user.city_tax_recipient_id = None
        user.extra_attack_count = 0
        await session.flush()
        from app.services.business_service import business_service
        await business_service._recalc_income(session, user, recalc_tax=True)

    async def _resolve_throne_challenge(
        self, session: AsyncSession, attacker: User, defender: User,
        progress_key: str, cd_key: str,
    ) -> dict:
        """Общая логика для challenge_emperor/challenge_king — один раунд боя
        за трон Империи (см. game_balance.EMPEROR_CHALLENGE_ROUNDS_TO_WIN).
        Побеждает серией из N побед ПОДРЯД — поражение любого раунда сбрасывает
        счёт этой пары в 0 (нужно начинать серию заново)."""
        from app.services.cooldown_service import cooldown_service
        from app.config.game_balance import EMPEROR_CHALLENGE_CD_SECONDS, EMPEROR_CHALLENGE_ROUNDS_TO_WIN
        from app.services.combat_service import fight_player
        from app.services.game.utils import notify_pvp_attack

        result = await fight_player(session, attacker, defender)
        await cooldown_service.set_cooldown(cd_key, EMPEROR_CHALLENGE_CD_SECONDS)

        if result["win"]:
            wins = await cooldown_service.redis.incr(progress_key)
            final = wins >= EMPEROR_CHALLENGE_ROUNDS_TO_WIN
            if final:
                await cooldown_service.redis.delete(progress_key)
            await notify_pvp_attack(
                attacker, defender, True, "emperor_challenge",
                result["attacker_power"], result["defender_power"],
            )
            await session.flush()
            return {
                "ok": True, "win": True, "final": final,
                "rounds_won": wins, "rounds_needed": EMPEROR_CHALLENGE_ROUNDS_TO_WIN,
                "attacker_power": result["attacker_power"], "defender_power": result["defender_power"],
                "defender_name": defender.full_name,
            }

        await cooldown_service.redis.delete(progress_key)
        await notify_pvp_attack(
            attacker, defender, False, "emperor_challenge",
            result["attacker_power"], result["defender_power"],
        )
        await session.flush()
        return {
            "ok": True, "win": False, "final": False,
            "rounds_won": 0, "rounds_needed": EMPEROR_CHALLENGE_ROUNDS_TO_WIN,
            "attacker_power": result["attacker_power"], "defender_power": result["defender_power"],
            "defender_name": defender.full_name,
        }

    async def challenge_emperor(
        self, session: AsyncSession, king: User, emperor_id: int
    ) -> dict:
        """Король, захвативший все города своей страны (сам + вассалы),
        бросает вызов действующему Императору этой страны за его трон.
        Нужно выиграть EMPEROR_CHALLENGE_ROUNDS_TO_WIN раз ПОДРЯД (раз в час
        за попытку) — поражение раунда сбрасывает счёт. На решающей победе
        Император теряет всё и уходит на этап Банды, победитель занимает трон."""
        if king.phase != "king":
            return {"ok": False, "reason": "Только для фазы Короля"}
        from app.utils.truce import is_truce_active
        if is_truce_active(king):
            return {"ok": False, "reason": "Во время перемирия нельзя атаковать"}

        if not await self._is_emperor_eligible(session, king):
            return {"ok": False, "reason": "Сначала захватите все города своей страны (сами + вассалы)"}

        from app.repositories.user_repo import user_repo
        emperor = await user_repo.get_by_id(session, emperor_id)
        if not emperor or emperor.phase != "emperor":
            return {"ok": False, "reason": "Император не найден"}
        from app.data.cities import DEFAULT_COUNTRY
        if (emperor.country or DEFAULT_COUNTRY) != (king.country or DEFAULT_COUNTRY):
            return {"ok": False, "reason": "Вызов — только Императору своей страны"}
        if is_truce_active(emperor):
            return {"ok": False, "reason": f"{emperor.full_name} находится под перемирием"}

        from app.services.cooldown_service import cooldown_service
        cd_key = cooldown_service.emperor_challenge_key(king.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"КД: {cooldown_service.format_ttl(ttl)}", "cd": ttl}

        progress_key = cooldown_service.emperor_challenge_progress_key(king.id, emperor.id)
        result = await self._resolve_throne_challenge(session, king, emperor, progress_key, cd_key)

        if result["win"] and result["final"]:
            await self._demote_to_gang(session, emperor)
            promo = await self._promote_to_emperor(session, king)
            result["promoted"] = True
            result["message"] = (
                f"👑 Ты победил Императора {emperor.full_name} в решающем "
                f"{result['rounds_needed']}/{result['rounds_needed']} раунде и занял его трон!\n\n"
                f"{promo['message']}"
            )
        return result

    async def challenge_king(
        self, session: AsyncSession, emperor: User, king_id: int
    ) -> dict:
        """Симметричное действие: Император атаковает Короля своей страны,
        который уже готов бросить ему вызов (захватил всю страну), чтобы
        сбить угрозу трону раньше, чем тот успеет ударить первым. Та же
        серия из N побед подряд — на решающей победе Король теряет всё и
        уходит на этап Банды."""
        if emperor.phase != "emperor":
            return {"ok": False, "reason": "Только для фазы Императора"}
        from app.utils.truce import is_truce_active
        if is_truce_active(emperor):
            return {"ok": False, "reason": "Во время перемирия нельзя атаковать"}

        from app.repositories.user_repo import user_repo
        king = await user_repo.get_by_id(session, king_id)
        if not king or king.phase != "king":
            return {"ok": False, "reason": "Король не найден"}
        from app.data.cities import DEFAULT_COUNTRY
        if (king.country or DEFAULT_COUNTRY) != (emperor.country or DEFAULT_COUNTRY):
            return {"ok": False, "reason": "Можно атаковать только Короля своей страны"}
        if not await self._is_emperor_eligible(session, king):
            return {"ok": False, "reason": "Этот Король ещё не готов бросить тебе вызов"}
        if is_truce_active(king):
            return {"ok": False, "reason": f"{king.full_name} находится под перемирием"}

        from app.services.cooldown_service import cooldown_service
        cd_key = cooldown_service.emperor_defend_key(emperor.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"КД: {cooldown_service.format_ttl(ttl)}", "cd": ttl}

        progress_key = cooldown_service.emperor_defend_progress_key(emperor.id, king.id)
        result = await self._resolve_throne_challenge(session, emperor, king, progress_key, cd_key)

        if result["win"] and result["final"]:
            await self._demote_to_gang(session, king)
            result["king_destroyed"] = True
            result["message"] = (
                f"👑 Ты в решающем {result['rounds_needed']}/{result['rounds_needed']} раунде "
                f"победил {king.full_name} — он потерял все города и вернулся на этап Банды!"
            )
        return result
