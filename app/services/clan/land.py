from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update as sa_update
from app.models.clan import Clan, ClanMember
from app.models.clan_land import ClanLandBuilding
from app.models.user import User
from app.config.game_balance import (
    CLAN_LAND_MAX_LEVEL,
    CLAN_LAND_UPGRADE_COST,
    CLAN_LAND_SLOTS,
    CLAN_LAND_BUILDINGS,
)
from app.services.clan.base import ClanBaseService


class ClanLandService(ClanBaseService):

    async def get_clan_land_buildings(
        self, session: AsyncSession, clan_id: int
    ) -> list[ClanLandBuilding]:
        result = await session.execute(
            select(ClanLandBuilding).where(ClanLandBuilding.clan_id == clan_id)
        )
        return list(result.scalars().all())

    async def get_building_counts(self, session: AsyncSession, clan_id: int) -> dict[str, int]:
        result = await session.execute(
            select(ClanLandBuilding.building_type, func.count())
            .where(ClanLandBuilding.clan_id == clan_id)
            .group_by(ClanLandBuilding.building_type)
        )
        return {btype: count for btype, count in result.all()}

    async def get_slots_used(self, session: AsyncSession, clan_id: int) -> int:
        return await session.scalar(
            select(func.count()).where(ClanLandBuilding.clan_id == clan_id)
        ) or 0

    def calc_bonuses(self, counts: dict[str, int]) -> dict[str, int]:
        """count → (тип бонуса, значение), лимит max_count применяется здесь."""
        bonuses = {btype: 0 for btype in CLAN_LAND_BUILDINGS}
        for btype, cfg in CLAN_LAND_BUILDINGS.items():
            count = counts.get(btype, 0)
            max_count = cfg.get("max_count")
            if max_count is not None:
                count = min(count, max_count)
            bonuses[btype] = count * cfg["bonus_per_unit"]
        return bonuses

    async def get_shop_discount_pct(self, session: AsyncSession, clan_id: int) -> int:
        cfg = CLAN_LAND_BUILDINGS["shop_discount"]
        count = await session.scalar(
            select(func.count()).where(
                ClanLandBuilding.clan_id == clan_id,
                ClanLandBuilding.building_type == "shop_discount",
            )
        ) or 0
        max_count = cfg.get("max_count")
        if max_count is not None:
            count = min(count, max_count)
        return count * cfg["bonus_per_unit"]

    def _user_values(self, bonuses: dict[str, int], is_owner: bool) -> dict:
        income_pct = bonuses.get("income_pct", 0)
        if is_owner:
            income_pct *= 2
        return {
            "clan_land_income_pct": income_pct,
            "clan_land_power_pct": bonuses.get("power", 0),
            "clan_land_fragment_pct": bonuses.get("fragment_gain", 0),
            "clan_land_mastery_pct": bonuses.get("mastery_gain", 0),
            "clan_land_power_mastery_bonus": bonuses.get("power_mastery", 0),
            "clan_land_speed_mastery_bonus": bonuses.get("speed_mastery", 0),
            "clan_land_cd_reduction_pct": bonuses.get("cd_reduction", 0),
        }

    async def recalc_land_bonuses(self, session: AsyncSession, clan_id: int) -> None:
        """Bulk-пересчитывает clan_land_* поля всем участникам клана.

        Глава клана получает x2 к своему вкладу в доход от зданий —
        считается отдельным апдейтом после общего.
        """
        clan = await session.scalar(select(Clan).where(Clan.id == clan_id))
        if not clan:
            return
        counts = await self.get_building_counts(session, clan_id)
        bonuses = self.calc_bonuses(counts)

        member_values = self._user_values(bonuses, is_owner=False)
        owner_values = self._user_values(bonuses, is_owner=True)

        subq = select(ClanMember.user_id).where(ClanMember.clan_id == clan_id)
        await session.execute(
            sa_update(User).where(User.id.in_(subq)).values(**member_values)
        )
        await session.execute(
            sa_update(User).where(User.id == clan.owner_id).values(**owner_values)
        )
        await session.flush()

        from app.services.business_service import business_service
        member_ids = await self.get_clan_member_ids(session, clan_id)
        users = (await session.execute(
            select(User).where(User.id.in_(member_ids)).order_by(User.id)
        )).scalars().all()
        for u in users:
            await business_service._recalc_income(session, u)

    async def apply_land_bonuses_to_user(self, session: AsyncSession, user: User, clan: Clan) -> None:
        """Версия для одного пользователя — используется при вступлении в клан."""
        counts = await self.get_building_counts(session, clan.id)
        bonuses = self.calc_bonuses(counts)
        is_owner = clan.owner_id == user.id
        for field, value in self._user_values(bonuses, is_owner).items():
            setattr(user, field, value)

    async def buy_land_upgrade(self, session: AsyncSession, clan: Clan, user: User) -> dict:
        rank = await self.get_member_rank(session, clan.id, user.id)
        if rank not in ("owner", "deputy"):
            return {"ok": False, "reason": "Только владелец или заместитель может улучшать землю"}

        next_level = clan.land_level + 1
        if next_level > CLAN_LAND_MAX_LEVEL:
            return {"ok": False, "reason": f"Земля на максимальном уровне ({CLAN_LAND_MAX_LEVEL})"}

        cost = CLAN_LAND_UPGRADE_COST[next_level]
        if clan.treasury < cost:
            return {"ok": False, "reason": f"Недостаточно в казне (нужно {cost:,})"}

        clan.treasury -= cost
        clan.land_level = next_level
        await session.flush()

        return {
            "ok": True,
            "new_level": next_level,
            "cost": cost,
            "slots": CLAN_LAND_SLOTS[next_level],
        }

    async def buy_land_building(
        self, session: AsyncSession, clan: Clan, user: User, building_type: str
    ) -> dict:
        cfg = CLAN_LAND_BUILDINGS.get(building_type)
        if not cfg:
            return {"ok": False, "reason": "Здание не найдено"}

        rank = await self.get_member_rank(session, clan.id, user.id)
        if rank not in ("owner", "deputy"):
            return {"ok": False, "reason": "Только владелец или заместитель может строить здания"}

        slots_used = await self.get_slots_used(session, clan.id)
        total_slots = CLAN_LAND_SLOTS.get(clan.land_level, 0)
        if slots_used >= total_slots:
            return {"ok": False, "reason": f"Нет свободных слотов ({slots_used}/{total_slots}). Улучшите землю"}

        max_count = cfg.get("max_count")
        if max_count is not None:
            counts = await self.get_building_counts(session, clan.id)
            if counts.get(building_type, 0) >= max_count:
                return {"ok": False, "reason": f"Достигнут лимит зданий этого типа ({max_count})"}

        cost = cfg["cost"]
        if clan.treasury < cost:
            return {"ok": False, "reason": f"Недостаточно в казне (нужно {cost:,})"}

        # Порядок блокировок при флаше — users до clan (см. _apply_clan_bonuses
        # в services/clan/base.py), иначе deadlock с конкурентными операциями,
        # которые тоже трогают users+clan (emperor.py, squad_repo и т.д.).
        session.add(ClanLandBuilding(clan_id=clan.id, building_type=building_type))
        await session.flush()

        await self.recalc_land_bonuses(session, clan.id)

        clan.treasury -= cost
        await session.flush()

        return {"ok": True, "name": cfg["name"], "cost": cost}

    async def demolish_land_building(
        self, session: AsyncSession, clan: Clan, user: User, building_type: str
    ) -> dict:
        """Сносит одно здание указанного типа, возвращая 50% его стоимости в казну.

        Здания одного типа взаимозаменяемы (бонус не зависит от конкретного
        экземпляра), поэтому сносим произвольное — так же, как строим по типу,
        а не по id. Освобождённый слот можно сразу занять другим зданием.
        """
        cfg = CLAN_LAND_BUILDINGS.get(building_type)
        if not cfg:
            return {"ok": False, "reason": "Здание не найдено"}

        rank = await self.get_member_rank(session, clan.id, user.id)
        if rank not in ("owner", "deputy"):
            return {"ok": False, "reason": "Только владелец или заместитель может сносить здания"}

        building = await session.scalar(
            select(ClanLandBuilding)
            .where(
                ClanLandBuilding.clan_id == clan.id,
                ClanLandBuilding.building_type == building_type,
            )
            .limit(1)
        )
        if not building:
            return {"ok": False, "reason": "Такого здания нет"}

        refund = cfg["cost"] // 2

        # Тот же порядок блокировок, что и в buy_land_building: сначала меняем
        # состав зданий и users (через recalc_land_bonuses), потом clan.treasury.
        await session.delete(building)
        await session.flush()

        await self.recalc_land_bonuses(session, clan.id)

        clan.treasury += refund
        await session.flush()

        return {"ok": True, "name": cfg["name"], "refund": refund}
