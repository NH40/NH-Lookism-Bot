import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.squad_member import SquadMember
from app.models.skill import UserMastery
from app.services.cooldown_service import cooldown_service
from app.services.potion_service import potion_service
from app.data.squad import RANKS_BY_ID, PHASE_RANKS, STAR_BONUS_PERCENT


# ── Конфиги рангов по фазам ─────────────────────────────────────────────────

PHASE_RANK_WEIGHTS: dict[str, dict[str, int]] = {
    "gang": {
        "E": 50, "D": 30, "C": 15, "B": 5,
    },
    "king": {
        "C": 40, "B": 30, "A": 20, "S": 10,
    },
    "fist": {
        "B": 35, "A": 35, "S": 30,
    },
    "emperor": {
        "B": 30, "A": 40, "S": 30,
    },
}

# Базовый множитель количества статистов от влияния
def _calc_recruit_count(influence: int, bonus_pct: int) -> int:
    """
    Базовое количество: influence / 100, минимум 1, максимум 20.
    Бонус вербовки увеличивает итог на %.
    """
    base = max(1, min(20, influence // 100))
    bonus = max(0, int(base * bonus_pct / 100))
    return base + bonus


async def _get_mastery(session: AsyncSession, user_id: int) -> UserMastery | None:
    result = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user_id)
    )
    return result.scalar_one_or_none()


def _get_speed_reduction(mastery: UserMastery | None) -> int:
    speed_levels = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
    if not mastery:
        return 0
    return speed_levels.get(mastery.speed, 0)


class SquadService:

    # ════════════════════════════════════════════════════════════════════════
    # ВЕРБОВКА
    # ════════════════════════════════════════════════════════════════════════

    async def recruit(
        self, session: AsyncSession, user: User
    ) -> dict:
        """
        Вербовка статистов.
        Количество = f(influence + recruit_count_bonus).
        Ранги = случайные по весам фазы.
        """
        cd_key = cooldown_service.recruit_key(user.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"Вербовка через {cooldown_service.format_ttl(ttl)}"}

        # Доступные ранги и их веса для текущей фазы
        phase_weights = PHASE_RANK_WEIGHTS.get(user.phase, PHASE_RANK_WEIGHTS["gang"])

        # Проверяем влияние — минимум для вербовки
        if user.influence < 10:
            return {"ok": False, "reason": "Недостаточно влияния (минимум 10)"}

        # Количество завербованных
        count = _calc_recruit_count(user.influence, user.recruit_count_bonus)

        # double_recruit — удваивает
        if user.double_recruit:
            count *= 2

        # Генерируем бойцов
        ranks = list(phase_weights.keys())
        weights = list(phase_weights.values())

        recruited = []
        for _ in range(count):
            rank = random.choices(ranks, weights=weights, k=1)[0]
            rank_cfg = RANKS_BY_ID.get(rank)
            if not rank_cfg:
                continue
            member = SquadMember(
                user_id=user.id,
                rank=rank,
                stars=0,
                base_power=rank_cfg.base_power,
            )
            session.add(member)
            recruited.append(rank)

        await session.flush()

        # Пересчёт боевой мощи
        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

        # КД с учётом скорости и титула focus
        mastery = await _get_mastery(session, user.id)
        speed_pct = _get_speed_reduction(mastery)
        from app.repositories.title_repo import title_repo
        has_focus = await title_repo.has_title(session, user.id, "focus")
        extra = 20 if has_focus else 0
        recruit_cd = cooldown_service.apply_speed_reduction(5 * 60, speed_pct, extra)
        await cooldown_service.set_cooldown(cd_key, recruit_cd)

        # Считаем статистику по рангам
        from collections import Counter
        rank_counts = Counter(recruited)

        return {
            "ok": True,
            "count": len(recruited),
            "rank_counts": dict(rank_counts),
        }

    async def buy_recruit(
        self, session: AsyncSession, user: User, rank: str, count: int
    ) -> dict:
        """Покупка конкретного ранга статистов за NHCoin (из магазина)."""
        from app.data.shop import RECRUIT_RANK_TO_ITEM, SHOP_MAP

        item_id = RECRUIT_RANK_TO_ITEM.get(rank)
        if not item_id:
            return {"ok": False, "reason": "Неизвестный ранг"}

        item = SHOP_MAP[item_id]
        discount = user.recruit_discount_percent
        price_per = max(1, int(item.price * (1 - discount / 100)))
        total = price_per * count

        if user.nh_coins < total:
            return {"ok": False, "reason": f"Недостаточно NHCoin (нужно {total:,})"}

        rank_cfg = RANKS_BY_ID.get(rank)
        if not rank_cfg:
            return {"ok": False, "reason": "Ранг не найден"}

        user.nh_coins -= total
        user.coins_spent += total

        for _ in range(count):
            member = SquadMember(
                user_id=user.id,
                rank=rank,
                stars=0,
                base_power=rank_cfg.base_power,
            )
            session.add(member)

        await session.flush()
        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

        return {"ok": True, "count": count, "total_cost": total}

    # ════════════════════════════════════════════════════════════════════════
    # ТРЕНИРОВКА
    # ════════════════════════════════════════════════════════════════════════

    async def train(self, session: AsyncSession, user: User) -> dict:
        """
        Тренировка отряда.
        - Охват = 10 + train_bonus_percent + prestige_train_bonus + зелье
        - Случайный выбор статистов (только те у кого < 5 звёзд)
        - Каждый получает от 1 до 3 звёзд (не превышая 5)
        - Шанс успеха тренировки: базово 50% + train_quality_bonus%
        """
        cd_key = cooldown_service.train_key(user.id)

        # double_train: проверяем вторую тренировку
        is_second = False
        if user.double_train:
            dkey = cooldown_service.double_train_key(user.id)
            if not await cooldown_service.is_on_cooldown(dkey):
                is_second = True

        if not is_second and await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"Тренировка через {cooldown_service.format_ttl(ttl)}"}

        # Все статисты у кого < 5 звёзд
        result = await session.execute(
            select(SquadMember).where(
                SquadMember.user_id == user.id,
                SquadMember.stars < 5,
            )
        )
        candidates = result.scalars().all()

        if not candidates:
            return {"ok": False, "reason": "Все статисты уже имеют 5 звёзд или отряд пуст"}

        # Охват тренировки (% от кандидатов)
        train_bonus = await potion_service.get_effective_train_bonus(session, user)
        coverage_pct = min(100, 10 + train_bonus)
        count_to_train = max(1, int(len(candidates) * coverage_pct / 100))

        # Случайный выбор
        to_train = random.sample(candidates, min(count_to_train, len(candidates)))

        # Шанс успеха тренировки: 50% базово + train_quality_bonus
        success_chance = min(95, 50 + user.train_quality_bonus)

        upgraded = 0
        failed = 0
        stars_added_total = 0

        for member in to_train:
            if random.randint(1, 100) <= success_chance:
                # Успех — добавляем от 1 до 3 звёзд
                max_add = 5 - member.stars
                stars_add = random.randint(1, min(3, max_add))
                member.stars += stars_add
                stars_added_total += stars_add
                upgraded += 1
            else:
                failed += 1

        await session.flush()

        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

        # КД тренировки с учётом скорости и focus
        mastery = await _get_mastery(session, user.id)
        speed_pct = _get_speed_reduction(mastery)
        from app.repositories.title_repo import title_repo
        has_focus = await title_repo.has_title(session, user.id, "focus")
        extra = 20 if has_focus else 0
        train_cd_seconds = cooldown_service.apply_speed_reduction(5 * 60, speed_pct, extra)

        if is_second:
            await cooldown_service.set_cooldown(
                cooldown_service.double_train_key(user.id), train_cd_seconds
            )
        else:
            await cooldown_service.set_cooldown(cd_key, train_cd_seconds)

        return {
            "ok": True,
            "trained": len(to_train),
            "upgraded": upgraded,
            "failed": failed,
            "stars_added": stars_added_total,
            "coverage_pct": coverage_pct,
            "success_chance": success_chance,
            "is_second": is_second,
        }

    # ════════════════════════════════════════════════════════════════════════
    # ОТОБРАЖЕНИЕ
    # ════════════════════════════════════════════════════════════════════════

    async def get_squad_summary(self, session: AsyncSession, user_id: int) -> str:
        result = await session.execute(
            select(SquadMember).where(SquadMember.user_id == user_id)
        )
        members = result.scalars().all()
        if not members:
            return "Отряд пуст"

        from collections import Counter
        rank_order = ["S", "A", "B", "C", "D", "E"]

        lines = []
        total = len(members)
        five_star = sum(1 for m in members if m.stars == 5)

        for rank in rank_order:
            rank_members = [m for m in members if m.rank == rank]
            if not rank_members:
                continue

            # Группируем по звёздам
            star_counts = Counter(m.stars for m in rank_members)
            star_parts = []
            for stars in range(5, -1, -1):
                c = star_counts.get(stars, 0)
                if c:
                    star_str = "⭐" * stars if stars > 0 else "☆"
                    star_parts.append(f"{star_str}×{c}")

            rank_cfg = RANKS_BY_ID.get(rank)
            lines.append(
                f"[{rank}] {rank_cfg.base_power:,} силы — {len(rank_members)} чел.\n"
                f"  {' | '.join(star_parts)}"
            )

        lines.append(f"\n👥 Всего: {total} | ⭐×5: {five_star}")
        return "\n".join(lines)


squad_service = SquadService()