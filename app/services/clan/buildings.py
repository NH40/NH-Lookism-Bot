from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update as sa_update
from app.models.clan import ClanMember

from app.models.clan import Clan
from app.models.clan_building import ClanRegionBuilding
from app.models.user import User
from app.config.game_balance import (
    CLAN_REGION_BUILDINGS,
    CLAN_REGION_BUILDING_MAX_LEVEL,
    CLAN_AP_INCOME_BONUS,
    CLAN_AP_INCOME_MAX,
    CLAN_AP_INCOME_COST,
    CLAN_AP_TRAIN_BONUS,
    CLAN_AP_TRAIN_MAX,
    CLAN_AP_TRAIN_COST,
    CLAN_AP_TICKET_BONUS,
    CLAN_AP_TICKET_MAX,
    CLAN_AP_TICKET_COST,
)
from app.services.clan.base import ClanBaseService


class ClanBuildingsService(ClanBaseService):

    async def get_clan_buildings(
        self, session: AsyncSession, clan_id: int
    ) -> list[ClanRegionBuilding]:
        result = await session.execute(
            select(ClanRegionBuilding).where(ClanRegionBuilding.clan_id == clan_id)
        )
        return list(result.scalars().all())

    def calc_total_income_per_member(self, buildings: list[ClanRegionBuilding]) -> int:
        total = 0
        for b in buildings:
            cfg = CLAN_REGION_BUILDINGS.get(b.building_type)
            if cfg and 0 < b.level <= CLAN_REGION_BUILDING_MAX_LEVEL:
                total += cfg["income_per_level"][b.level]
        return total

    async def recalc_clan_region_income(
        self, session: AsyncSession, clan_id: int, has_region: bool
    ) -> None:
        """Bulk-обновляет clan_region_income через субзапрос — без загрузки участников."""
        income = 0
        if has_region:
            buildings = await self.get_clan_buildings(session, clan_id)
            income = self.calc_total_income_per_member(buildings)
        subq = select(ClanMember.user_id).where(ClanMember.clan_id == clan_id)
        await session.execute(
            sa_update(User).where(User.id.in_(subq)).values(clan_region_income=income)
        )
        await session.flush()

    async def buy_or_upgrade_building(
        self,
        session: AsyncSession,
        clan: Clan,
        user: User,
        building_type: str,
    ) -> dict:
        cfg = CLAN_REGION_BUILDINGS.get(building_type)
        if not cfg:
            return {"ok": False, "reason": "Здание не найдено"}

        building = await session.scalar(
            select(ClanRegionBuilding).where(
                ClanRegionBuilding.clan_id == clan.id,
                ClanRegionBuilding.building_type == building_type,
            )
        )
        next_level = 1 if building is None else building.level + 1

        if next_level > CLAN_REGION_BUILDING_MAX_LEVEL:
            return {"ok": False, "reason": f"Здание на максимальном уровне ({CLAN_REGION_BUILDING_MAX_LEVEL})"}

        ap_cost = cfg["ap_cost_per_level"][next_level]
        if clan.treasury_ap < ap_cost:
            return {
                "ok": False,
                "reason": f"Недостаточно ОА в казне (нужно {ap_cost}, есть {clan.treasury_ap})",
            }

        clan.treasury_ap -= ap_cost
        if building is None:
            building = ClanRegionBuilding(clan_id=clan.id, building_type=building_type, level=1)
            session.add(building)
        else:
            building.level = next_level
        await session.flush()

        await self.recalc_clan_region_income(session, clan.id, has_region=True)

        return {
            "ok": True,
            "name": cfg["name"],
            "new_level": next_level,
            "income_per_member": cfg["income_per_level"][next_level],
            "ap_spent": ap_cost,
        }

    async def deposit_ap(
        self, session: AsyncSession, clan: Clan, user: User, amount: int
    ) -> dict:
        if amount <= 0:
            return {"ok": False, "reason": "Сумма должна быть больше 0"}
        if amount < 10:
            return {"ok": False, "reason": "Минимальный взнос — 10 ОА"}
        if user.activity_points < amount:
            return {
                "ok": False,
                "reason": f"Недостаточно ОА (есть {user.activity_points})",
            }
        user.activity_points -= amount
        clan.treasury_ap += amount
        await session.flush()
        return {"ok": True}

    async def buy_ap_upgrade(
        self, session: AsyncSession, clan: Clan, user: User, upgrade_type: str
    ) -> dict:
        new_treasury_ap = None
        new_ap_income_circles = new_ap_train_circles = new_ap_ticket_circles = None

        if upgrade_type == "income":
            if clan.ap_income_circles >= CLAN_AP_INCOME_MAX:
                return {
                    "ok": False,
                    "reason": f"Максимум достигнут (+{CLAN_AP_INCOME_MAX * CLAN_AP_INCOME_BONUS}% к доходу)",
                }
            cost = CLAN_AP_INCOME_COST
            if clan.treasury_ap < cost:
                return {"ok": False, "reason": f"Недостаточно ОА (нужно {cost}, есть {clan.treasury_ap})"}
            new_treasury_ap = clan.treasury_ap - cost
            new_ap_income_circles = clan.ap_income_circles + 1
        elif upgrade_type == "train":
            if clan.ap_train_circles >= CLAN_AP_TRAIN_MAX:
                return {
                    "ok": False,
                    "reason": f"Максимум достигнут (+{CLAN_AP_TRAIN_MAX * CLAN_AP_TRAIN_BONUS}% к тренировкам)",
                }
            cost = CLAN_AP_TRAIN_COST
            if clan.treasury_ap < cost:
                return {"ok": False, "reason": f"Недостаточно ОА (нужно {cost}, есть {clan.treasury_ap})"}
            new_treasury_ap = clan.treasury_ap - cost
            new_ap_train_circles = clan.ap_train_circles + 1
        elif upgrade_type == "ticket":
            if clan.ap_ticket_circles >= CLAN_AP_TICKET_MAX:
                return {
                    "ok": False,
                    "reason": f"Максимум достигнут (+{CLAN_AP_TICKET_MAX * CLAN_AP_TICKET_BONUS}% шанс тикета)",
                }
            cost = CLAN_AP_TICKET_COST
            if clan.treasury_ap < cost:
                return {"ok": False, "reason": f"Недостаточно ОА (нужно {cost}, есть {clan.treasury_ap})"}
            new_treasury_ap = clan.treasury_ap - cost
            new_ap_ticket_circles = clan.ap_ticket_circles + 1
        else:
            return {"ok": False, "reason": "Неизвестное улучшение"}

        # Сначала применяем бонусы к users (через override, ещё до мутации clan),
        # затем мутируем clan — порядок блокировок users->clan, как везде
        # (см. _apply_clan_bonuses — иначе deadlock с конкурентными операциями,
        # которые тоже трогают users+clan, например emperor.py при дропе карты).
        await self._apply_clan_bonuses(
            session, clan,
            ap_income_circles=new_ap_income_circles,
            ap_train_circles=new_ap_train_circles,
            ap_ticket_circles=new_ap_ticket_circles,
        )

        clan.treasury_ap = new_treasury_ap
        if new_ap_income_circles is not None:
            clan.ap_income_circles = new_ap_income_circles
        if new_ap_train_circles is not None:
            clan.ap_train_circles = new_ap_train_circles
        if new_ap_ticket_circles is not None:
            clan.ap_ticket_circles = new_ap_ticket_circles

        await session.flush()
        return {"ok": True, "upgrade_type": upgrade_type}
