"""PromotionsMixin — переходы между фазами игры (повышение / понижение / уничтожение)."""
import random
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

FIST_MIN_CITIES = 5
FIST_CITY_SIZES = [8, 16, 32, 64]

FIST_BOT_CONFIGS = [
    {"name": "Рю",  "ratio": 0.80},
    {"name": "Со",  "ratio": 0.90},
    {"name": "Чан", "ratio": 1.00},
    {"name": "Пэк", "ratio": 1.10},
    {"name": "Ли",  "ratio": 1.20},
]


class PromotionsMixin:

    async def _demote_fist_to_king(
        self, session: AsyncSession, user: User, king_cities_lost: int = 0
    ) -> None:
        await self._take_fist_cities_from(session, user, 9999)
        user.fist_cities_count = 0
        if king_cities_lost > 0:
            await self._take_king_cities_from(session, user, king_cities_lost)
        user.phase = "king"
        user.king_cities_count = await self._count_my_king_cities(session, user.id)
        user.extra_attack_count = await self._get_max_extra_attacks_async(session, user)
        from sqlalchemy import delete as sql_delete
        from app.models.king_bot import KingBot
        await session.execute(sql_delete(KingBot).where(KingBot.user_id == user.id))
        await session.flush()
        need = max(0, 10 - user.king_cities_count)
        try:
            from app.bot_instance import get_bot
            bot = get_bot()
            if bot and user.notifications_enabled and getattr(user, "notif_cities", True):
                need_text = (
                    f"Осталось городов: <b>{user.king_cities_count}/10</b>. "
                    f"Нужно захватить ещё <b>{need}</b>."
                    if need > 0
                    else "У вас уже 10 городов — можете снова стать Кулаком!"
                )
                await bot.send_message(
                    user.tg_id,
                    "⚠️ <b>Вы потеряли слишком много городов!</b>\n\n"
                    f"Вы понижены до фазы Короля.\n{need_text}",
                    parse_mode="HTML",
                )
        except Exception:
            pass

    async def _promote_to_king(
        self, session: AsyncSession, user: User, city
    ) -> dict:
        user.phase = "king"
        user.king_cities_count = 1
        user.extra_attack_count = await self._get_max_extra_attacks_async(session, user)
        from sqlalchemy import delete as sql_delete, update as sql_update
        from app.models.king_bot import KingBot
        from app.models.city import District
        await session.execute(sql_delete(KingBot).where(KingBot.user_id == user.id))

        # Город мог уже принадлежать другому королю (он освободил районы,
        # когда сам получил корону/дорос до Императора, но трон — City.owner_id —
        # остался за ним). Банда, заново заполнившая этот город, НЕ получает
        # корону бесплатно — только бой за трон, как и при захвате районов
        # уже действующего короля. Если city.owner_id пуст — это первый
        # король этого города, трон достаётся без боя, как раньше.
        title_message = ""
        if city.owner_id and city.owner_id != user.id:
            from app.repositories.user_repo import user_repo
            reigning_king = await user_repo.get_by_id(session, city.owner_id)
            if reigning_king:
                from app.services.combat_service import fight_player
                from app.services.game.utils import apply_battle_casualties
                fight = await fight_player(session, user, reigning_king)
                await apply_battle_casualties(session, user, reigning_king, fight["win"])
                if fight["win"]:
                    city.owner_id = user.id
                    await self._recalc_city_tax_for_city_residents(session, city.id)
                    title_message = "\n\n👑 Вы также выиграли битву за трон и забрали корону города!"
                else:
                    title_message = (
                        f"\n\n💀 Но вы проиграли битву за трон — корона осталась "
                        f"у {reigning_king.full_name}. Часть статистов и карточек погибла в бою."
                    )
            else:
                city.owner_id = user.id
        else:
            city.owner_id = user.id

        # Трон города переходит новому Королю (city.owner_id — считается для
        # налога/вассалитета/права на Императора), но сами районы освобождаются
        # обратно под простых ботов: банды продолжают соревноваться за этот
        # город, как за любой другой ещё не захваченный (см. gang_attack_pvp —
        # без этого освобождения районы навсегда "зависают" ничейными
        # соперниками, которых нельзя атаковать, т.к. их владелец — Король —
        # больше не участвует в фазе Банды).
        await session.execute(
            sql_update(District)
            .where(District.city_id == city.id, District.is_captured == True)
            .values(owner_id=None, is_captured=False)
        )
        city.captured_districts = 0
        city.is_fully_captured = False

        await session.flush()
        return {
            "ok": True, "promoted": True, "new_phase": "king",
            "message": (
                f"🎉 Вы захватили <b>{city.name}</b> и стали Королём!\n\n"
                f"Захватите все города своей страны, чтобы стать Императором."
                + title_message
            )
        }

    async def _release_king_districts(self, session: AsyncSession, user: User) -> None:
        """Release all king/gang-phase districts on fist promotion."""
        from sqlalchemy import update as sql_update, select, func
        from app.models.city import City, District

        districts_r = await session.execute(
            select(District.id, District.city_id)
            .join(City, City.id == District.city_id)
            .where(
                District.owner_id == user.id,
                District.is_captured == True,
                City.phase != "fist",
            )
        )
        rows = districts_r.all()
        if not rows:
            return

        district_ids = [r[0] for r in rows]
        city_ids = set(r[1] for r in rows)

        await session.execute(
            sql_update(District)
            .where(District.id.in_(district_ids))
            .values(owner_id=None, is_captured=False)
        )
        await session.flush()

        for city_id in city_ids:
            city = await session.get(City, city_id)
            if city:
                real_captured = await session.scalar(
                    select(func.count(District.id)).where(
                        District.city_id == city_id,
                        District.is_captured == True,
                    )
                ) or 0
                city.captured_districts = real_captured
                if city.owner_id == user.id:
                    city.owner_id = None
                    city.is_fully_captured = False

        from app.services.business_service import business_service
        await business_service.apply_capture_influence(session, user, -len(district_ids))
        await business_service._recalc_income(session, user, recalc_tax=True)
        await session.flush()

    async def _promote_to_fist(self, session: AsyncSession, user: User) -> dict:
        user.phase = "fist"
        user.fist_cities_count = 0
        user.extra_attack_count = await self._get_max_extra_attacks_async(session, user)
        total_granted = 0
        for _ in range(FIST_MIN_CITIES):
            city_size = random.choice(FIST_CITY_SIZES)
            total_granted += city_size
            await self._give_fist_city_one(session, user, city_size)
        user.fist_cities_count = FIST_MIN_CITIES
        from sqlalchemy import delete as sql_delete
        from app.models.city import FistBot
        await session.execute(sql_delete(FistBot).where(FistBot.challenger_id == user.id))
        from app.services.business_service import business_service
        await business_service.apply_capture_influence(session, user, total_granted)
        await business_service._recalc_income(session, user, recalc_tax=True)
        await session.flush()
        return {
            "ok": True, "promoted": True, "new_phase": "fist",
            "message": (
                "✊ Вы набрали районы в 10 городах и стали Кулаком!\n\n"
                "Победите 10 кулаков чтобы стать Императором."
            )
        }

    async def _promote_to_emperor(self, session: AsyncSession, user: User) -> dict:
        from sqlalchemy import delete as sql_delete
        from app.models.emperor_gang import EmperorGangRecord
        from app.models.gapren import GaprenChallenge
        await session.execute(
            sql_delete(EmperorGangRecord).where(EmperorGangRecord.user_id == user.id)
        )
        await session.execute(
            sql_delete(GaprenChallenge).where(GaprenChallenge.user_id == user.id)
        )
        user.phase = "emperor"
        user.extra_attack_count = 0
        user.emperor_entry_power = user.combat_power

        # Как и при повышении банда→король (см. _promote_to_king): районы,
        # которые Император держал как Король, освобождаются под ботов, чтобы
        # другие банды/короли снова могли за них соревноваться — но, В ОТЛИЧИЕ
        # от _release_king_districts (который чистит City.owner_id — так было
        # нужно для убранного из игры этапа Кулака), трон города (City.owner_id)
        # у Императора НЕ отбирается: город навсегда остаётся его, и он
        # продолжает получать долю чужого дохода с этих районов через
        # существующий налог города (city_tax_percent/city_tax_recipient_id,
        # см. _recalc_city_tax) — Император не теряет город, просто перестаёт
        # держать в нём районы лично.
        from sqlalchemy import update as sql_update, select as sql_select, func as sql_func
        from app.models.city import City, District

        districts_r = await session.execute(
            sql_select(District.id, District.city_id)
            .join(City, City.id == District.city_id)
            .where(
                District.owner_id == user.id,
                District.is_captured == True,
                City.phase != "fist",
            )
        )
        rows = districts_r.all()
        if rows:
            district_ids = [r[0] for r in rows]
            city_ids = set(r[1] for r in rows)

            await session.execute(
                sql_update(District)
                .where(District.id.in_(district_ids))
                .values(owner_id=None, is_captured=False)
            )
            await session.flush()

            for city_id in city_ids:
                real_captured = await session.scalar(
                    sql_select(sql_func.count(District.id)).where(
                        District.city_id == city_id,
                        District.is_captured == True,
                    )
                ) or 0
                city = await session.get(City, city_id)
                if city:
                    city.captured_districts = real_captured
                    # city.owner_id намеренно НЕ трогаем — трон остаётся у Императора.

        await session.flush()
        return {
            "ok": True, "promoted": True, "new_phase": "emperor",
            "message": "👑 Вы захватили все земли своей страны и стали Императором!"
        }

    async def _destroy_gang(self, session: AsyncSession, user: User) -> dict:
        from app.services.prestige_service import prestige_service
        await prestige_service._reset_progress(session, user, keep_ui=True, keep_progress=True)
        return {"ok": True, "destroyed": True, "message": "💀 Ваша банда уничтожена! Начинайте сначала."}

    async def _destroy_king(self, session: AsyncSession, user: User) -> dict:
        from sqlalchemy import update as sql_update
        from app.models.city import City
        # Фикс "фантомного короля" — сброс прогресса раньше не чистил City.owner_id,
        # погибший король оставался вечным получателем городского налога.
        await session.execute(
            sql_update(City).where(City.owner_id == user.id).values(owner_id=None)
        )
        await session.execute(
            sql_update(User).where(User.suzerain_id == user.id).values(suzerain_id=None)
        )
        user.vassal_count = 0
        from app.services.prestige_service import prestige_service
        await prestige_service._reset_progress(session, user, keep_ui=True, keep_progress=True)
        return {"ok": True, "destroyed": True, "message": "💀 Вы потеряли все города!"}
