"""
Бизнес-логика системы Походов.

Формулы:
  power_ratio = avg_power / required_power_per_statist

  success_chance = clamp(base_success + power_ratio * POWER_BONUS_FACTOR,
                         MIN_SUCCESS_CHANCE, MAX_SUCCESS_CHANCE)

  При успехе:
    survival_pct = clamp(BASE_SURVIVAL_ON_SUCCESS + power_ratio * SURVIVAL_FACTOR,
                         MIN_SURVIVAL_SUCCESS, MAX_SURVIVAL_RATE)

  При провале:
    survival_pct = clamp(BASE_SURVIVAL_ON_FAIL + power_ratio * SURVIVAL_FACTOR_FAIL,
                         MIN_SURVIVAL_FAIL, MAX_SURVIVAL_RATE // 2)

  resource_gained = statist_count * duration_hours * base_per_statist_per_hour * reward_multiplier
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.campaigns import (
    BASE_SURVIVAL_ON_FAIL,
    BASE_SURVIVAL_ON_SUCCESS,
    CAMPAIGN_RANK_MAP,
    CAMPAIGN_RESOURCE_MAP,
    MAX_ACTIVE_CAMPAIGNS,
    MAX_STATISTS_PER_CAMPAIGN,
    MAX_SUCCESS_CHANCE,
    MAX_SURVIVAL_RATE,
    MIN_SURVIVAL_FAIL,
    MIN_SURVIVAL_SUCCESS,
    MIN_SUCCESS_CHANCE,
    POWER_BONUS_FACTOR,
    SURVIVAL_FACTOR,
    SURVIVAL_FACTOR_FAIL,
)
from app.models.campaign import Campaign
from app.models.squad_member import SquadMember
from app.models.user import User
from app.repositories.campaign_repo import campaign_repo

if TYPE_CHECKING:
    pass


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _calc_success_chance(avg_power: int, rank: str) -> int:
    """Шанс успешного сбора ресурса в %."""
    cfg = CAMPAIGN_RANK_MAP[rank]
    if cfg.required_power_per_statist == 0:
        ratio = 1.0
    else:
        ratio = avg_power / cfg.required_power_per_statist
    chance = cfg.base_success_chance + ratio * POWER_BONUS_FACTOR
    return int(_clamp(chance, MIN_SUCCESS_CHANCE, MAX_SUCCESS_CHANCE))


def _calc_survival_pct(avg_power: int, rank: str, success: bool) -> int:
    """Процент выживших статистов."""
    cfg = CAMPAIGN_RANK_MAP[rank]
    if cfg.required_power_per_statist == 0:
        ratio = 1.0
    else:
        ratio = avg_power / cfg.required_power_per_statist

    if success:
        pct = BASE_SURVIVAL_ON_SUCCESS + ratio * SURVIVAL_FACTOR
        return int(_clamp(pct, MIN_SURVIVAL_SUCCESS, MAX_SURVIVAL_RATE))
    else:
        pct = BASE_SURVIVAL_ON_FAIL + ratio * SURVIVAL_FACTOR_FAIL
        return int(_clamp(pct, MIN_SURVIVAL_FAIL, MAX_SURVIVAL_RATE // 2))


def _calc_resource(
    statist_count: int,
    duration_hours: int,
    rank: str,
    resource_type: str,
) -> int:
    """Количество ресурса при успешном походе."""
    res_cfg = CAMPAIGN_RESOURCE_MAP[resource_type]
    rank_cfg = CAMPAIGN_RANK_MAP[rank]
    base = statist_count * duration_hours * res_cfg.base_per_statist_per_hour
    return max(1, int(base * rank_cfg.reward_multiplier))


# ── Основные операции ─────────────────────────────────────────────────────────

class CampaignService:

    async def get_active_campaigns(
        self, session: AsyncSession, user_id: int
    ) -> list[Campaign]:
        return await campaign_repo.get_active(session, user_id)

    async def get_finished_campaigns(
        self, session: AsyncSession, user_id: int
    ) -> list[Campaign]:
        return await campaign_repo.get_finished(session, user_id)

    async def can_start(self, session: AsyncSession, user_id: int) -> tuple[bool, str]:
        """Проверяет, можно ли начать новый поход."""
        count = await campaign_repo.count_active(session, user_id)
        if count >= MAX_ACTIVE_CAMPAIGNS:
            return False, f"Уже активно {count}/{MAX_ACTIVE_CAMPAIGNS} походов"
        return True, ""

    async def get_available_statists(
        self,
        session: AsyncSession,
        user_id: int,
        statist_rank: str | None = None,
    ) -> list[SquadMember]:
        """Статисты, НЕ занятые в активных походах. Опционально — только указанного ранга."""
        active = await campaign_repo.get_active(session, user_id)
        busy_ids: set[int] = set()
        for c in active:
            try:
                busy_ids.update(json.loads(c.statist_ids))
            except Exception:
                pass

        q = select(SquadMember).where(SquadMember.user_id == user_id)
        if statist_rank:
            q = q.where(SquadMember.rank == statist_rank)
        result = await session.execute(q)
        all_members = list(result.scalars().all())
        return [m for m in all_members if m.id not in busy_ids]

    async def get_available_by_rank(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> dict[str, list[SquadMember]]:
        """Свободные статисты, сгруппированные по рангу."""
        all_available = await self.get_available_statists(session, user_id)
        grouped: dict[str, list[SquadMember]] = {}
        for m in all_available:
            grouped.setdefault(m.rank, []).append(m)
        return grouped

    async def start_campaign(
        self,
        session: AsyncSession,
        user: User,
        resource_type: str,
        rank: str,
        duration_hours: int,
        statist_count: int,
        statist_rank: str | None = None,
    ) -> dict:
        """
        Запускает поход.
        Возвращает {"ok": True/False, "reason": str, "campaign": Campaign|None}

        !! SELECT FOR UPDATE блокирует строку пользователя — параллельный запрос
        будет ждать и после разблокировки увидит актуальное число активных походов.
        """
        if resource_type not in CAMPAIGN_RESOURCE_MAP:
            return {"ok": False, "reason": "Неизвестный ресурс", "campaign": None}
        if rank not in CAMPAIGN_RANK_MAP:
            return {"ok": False, "reason": "Неизвестный ранг", "campaign": None}
        if statist_count <= 0:
            return {"ok": False, "reason": "Нужно выбрать хотя бы 1 статиста", "campaign": None}

        # Блокируем строку пользователя — никакой второй запрос не создаст поход
        # пока мы не закоммитим транзакцию.
        locked_user = await session.scalar(
            select(User).where(User.id == user.id).with_for_update()
        )
        if not locked_user:
            return {"ok": False, "reason": "Пользователь не найден", "campaign": None}

        # Перечитываем число активных походов под блокировкой
        active_count = await campaign_repo.count_active(session, locked_user.id)
        if active_count >= MAX_ACTIVE_CAMPAIGNS:
            return {
                "ok": False,
                "reason": f"Уже активно {active_count}/{MAX_ACTIVE_CAMPAIGNS} походов",
                "campaign": None,
            }

        available = await self.get_available_statists(session, locked_user.id, statist_rank)
        if statist_count > len(available):
            rank_label = f" ранга {statist_rank}" if statist_rank else ""
            return {
                "ok": False,
                "reason": f"Недостаточно свободных статистов{rank_label} (доступно {len(available)})",
                "campaign": None,
            }
        statist_count = min(statist_count, MAX_STATISTS_PER_CAMPAIGN)

        # Берём самых слабых (по base_power) — чтобы сильных не трогать
        available_sorted = sorted(available, key=lambda m: m.base_power)
        chosen = available_sorted[:statist_count]
        chosen_ids = [m.id for m in chosen]

        avg_power = int(sum(m.base_power for m in chosen) / len(chosen)) if chosen else 0

        ends_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)

        camp = await campaign_repo.create(
            session=session,
            user_id=locked_user.id,
            resource_type=resource_type,
            rank=rank,
            duration_hours=duration_hours,
            statist_ids=chosen_ids,
            avg_power=avg_power,
            ends_at=ends_at,
        )

        return {"ok": True, "reason": "", "campaign": camp}

    async def collect_campaign(
        self, session: AsyncSession, user: User, campaign_id: int
    ) -> dict:
        """
        Забирает результат завершённого похода.
        Возвращает данные о результате.

        !! SELECT FOR UPDATE блокирует строку похода — двойной сбор невозможен.
        """
        # Блокируем конкретный поход — параллельный запрос будет ждать,
        # после разблокировки увидит status!=finished и откажет.
        camp = await session.scalar(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.user_id == user.id,
            ).with_for_update()
        )
        if not camp:
            return {"ok": False, "reason": "Поход не найден"}
        if camp.status != "finished":
            return {"ok": False, "reason": "Поход ещё не завершён"}

        # Начисляем ресурс
        resource_type = camp.resource_type
        gained = camp.resource_gained
        if gained > 0 and hasattr(user, resource_type):
            current = getattr(user, resource_type, 0)
            setattr(user, resource_type, current + gained)

        # Возвращаем выживших статистов (они уже помечены в statist_ids, просто "разблокируются")
        # Удаляем навсегда погибших из squad
        if camp.statists_lost > 0:
            try:
                all_ids = json.loads(camp.statist_ids)
                returned_count = camp.statists_returned
                # Убиваем тех, кто не вернулся (берём первых statists_lost по списку)
                dead_ids = all_ids[returned_count:]
                if dead_ids:
                    from sqlalchemy import delete as sa_delete
                    await session.execute(
                        sa_delete(SquadMember).where(SquadMember.id.in_(dead_ids))
                    )
                    # Пересчитываем боевую мощь
                    from app.repositories.squad_repo import squad_repo
                    await squad_repo.update_user_combat_power(session, user)
            except Exception:
                pass

        result = {
            "ok": True,
            "success": camp.success,
            "resource_type": resource_type,
            "resource_gained": gained,
            "statists_sent": camp.statist_count,
            "statists_returned": camp.statists_returned,
            "statists_lost": camp.statists_lost,
            "rank": camp.rank,
            "duration_hours": camp.duration_hours,
        }

        await campaign_repo.delete(session, camp)
        return result

    # ── Вызывается планировщиком ──────────────────────────────────────────────

    async def process_expired(self, session: AsyncSession, camp: Campaign) -> dict:
        """
        Рассчитывает итог похода и помечает его как finished.
        Возвращает результат для уведомления игрока.
        """
        success_chance = _calc_success_chance(camp.avg_power, camp.rank)
        roll = random.randint(1, 100)
        success = roll <= success_chance

        survival_pct = _calc_survival_pct(camp.avg_power, camp.rank, success)
        # Небольшая случайность: ±10% от survival_pct
        jitter = random.randint(-10, 10)
        effective_survival = int(_clamp(survival_pct + jitter, 0, 100))

        returned = round(camp.statist_count * effective_survival / 100)
        returned = max(0, min(returned, camp.statist_count))
        lost = camp.statist_count - returned

        resource_gained = 0
        if success:
            resource_gained = _calc_resource(
                statist_count=camp.statist_count,
                duration_hours=camp.duration_hours,
                rank=camp.rank,
                resource_type=camp.resource_type,
            )
            # Случайность награды: 80%–120%
            factor = random.uniform(0.8, 1.2)
            resource_gained = max(0, int(resource_gained * factor))

        await campaign_repo.finish(
            session=session,
            campaign=camp,
            success=success,
            resource_gained=resource_gained,
            statists_returned=returned,
            statists_lost=lost,
        )

        return {
            "success": success,
            "success_chance": success_chance,
            "roll": roll,
            "survival_pct": effective_survival,
            "resource_gained": resource_gained,
            "statists_returned": returned,
            "statists_lost": lost,
        }

    # ── Вспомогательные для UI ────────────────────────────────────────────────

    def calc_preview(self, avg_power: int, rank: str, resource_type: str,
                     duration_hours: int, statist_count: int) -> dict:
        """Предварительный расчёт для отображения в интерфейсе."""
        success_chance = _calc_success_chance(avg_power, rank)
        survival_on_success = _calc_survival_pct(avg_power, rank, True)
        survival_on_fail = _calc_survival_pct(avg_power, rank, False)
        resource = _calc_resource(statist_count, duration_hours, rank, resource_type)
        return {
            "success_chance": success_chance,
            "survival_on_success": survival_on_success,
            "survival_on_fail": survival_on_fail,
            "resource_max": resource,
        }


campaign_service = CampaignService()
