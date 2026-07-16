import random
from collections import Counter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.skill import UserMastery
from app.repositories.squad_repo import squad_repo
from app.services.cooldown_service import cooldown_service
from app.services.potion_service import potion_service
from app.data.squad import RANKS_BY_ID, PHASE_RANKS, STAR_BONUS_PERCENT
from app.constants.squad import PHASE_RANK_WEIGHTS
from app.utils.squad_math import sample_binomial, split_three_way, largest_remainder_alloc
from app.config.game_balance import (
    TRAIN_BASE_COVERAGE, TRAIN_BASE_SUCCESS_CHANCE, TRAIN_MAX_SUCCESS_CHANCE,
    RECRUIT_INFLUENCE_TIERS,
)


def _calc_recruit_count(influence: int, bonus_pct: int) -> int:
    """Базовое количество по тирам влияния; bonus_pct увеличивает итог на %."""
    base = 1
    for threshold, count in RECRUIT_INFLUENCE_TIERS:
        if influence >= threshold:
            base = count
    bonus = max(0, int(base * bonus_pct / 100))
    return base + bonus


async def _get_mastery(session: AsyncSession, user_id: int) -> UserMastery | None:
    result = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user_id)
    )
    return result.scalar_one_or_none()


def _get_speed_reduction(
    mastery: UserMastery | None, multiplier: float = 1.0, clan_bonus: int = 0, force_max: bool = False
) -> int:
    speed_levels = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
    raw = mastery.speed if mastery else 0
    # force_max — Слава: Чарльз Чоя «Невидимые атаки» (авто мастерство скорости 4 ур.)
    speed_level = 4 if force_max else min(4, raw + clan_bonus)
    return int(speed_levels.get(speed_level, 0) * multiplier)


class SquadService:

    # ════════════════════════════════════════════════════════════════════════
    # ВЕРБОВКА
    # ════════════════════════════════════════════════════════════════════════

    async def recruit(
        self, session: AsyncSession, user: User, bypass_cd: bool = False
    ) -> dict:
        """
        Вербовка статистов.
        Количество = f(influence + recruit_count_bonus).
        Ранги = случайные по весам фазы.

        bypass_cd — используется только Ультра Инстинктом при бонусе сета Гана
        «Истинный ультра инстинкт» (х2 вербовка за тик).
        """
        cd_key = cooldown_service.recruit_key(user.id)
        if not bypass_cd and await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"Вербовка через {cooldown_service.format_ttl(ttl)}"}

        # Доступные ранги и их веса для текущей фазы
        phase_weights = dict(PHASE_RANK_WEIGHTS.get(user.phase, PHASE_RANK_WEIGHTS["gang"]))

        # Эффективное влияние с учётом зелья влияния
        effective_influence = await potion_service.get_effective_influence(session, user)

        # Проверяем влияние — минимум для вербовки
        if effective_influence < 10:
            return {"ok": False, "reason": "Недостаточно влияния (минимум 10)"}

        # Количество завербованных
        count = _calc_recruit_count(effective_influence, user.recruit_count_bonus)

        # double_recruit — удваивает
        if user.double_recruit:
            count *= 2

        # Слава — Гапрена «Герой»: ×2 получение статистов из любых источников
        if getattr(user, "fame_gaprena_hero", False):
            count *= 2

        # Титул «Отбор» — ×3 к весам двух сильнейших (наиредких) рангов фазы
        from app.repositories.title_repo import title_repo as _title_repo
        if await _title_repo.has_title(session, user.id, "selection"):
            # Сортируем по весу по возрастанию: первые = наиредкие = сильнейшие
            rarest_ranks = sorted(phase_weights, key=lambda r: phase_weights[r])[:2]
            for top_rank in rarest_ranks:
                phase_weights[top_rank] = phase_weights[top_rank] * 3

        # Генерируем бойцов
        ranks = list(phase_weights.keys())
        weights = list(phase_weights.values())

        selected_ranks = random.choices(ranks, weights=weights, k=count)
        rank_counts = Counter(r for r in selected_ranks if RANKS_BY_ID.get(r))
        total_recruited = sum(rank_counts.values())

        # По группе на ранг (не по строке на бойца) — O(рангов), не O(count)
        for rank, cnt in rank_counts.items():
            rank_cfg = RANKS_BY_ID[rank]
            await squad_repo.add_count(session, user.id, rank, 0, cnt, base_power=rank_cfg.base_power)

        # Счётчик достижений
        user.total_statists_recruited = (user.total_statists_recruited or 0) + total_recruited

        # Личная активность (Алея/Зал славы)
        from app.utils.region_activity import record as record_activity
        await record_activity(session, user.id, "recruit")

        # Пересчёт боевой мощи
        await squad_repo.update_user_combat_power(session, user)

        # КД с учётом скорости и титула focus
        mastery = await _get_mastery(session, user.id)
        speed_pct = _get_speed_reduction(
            mastery, user.skill_path_bonus_multiplier,
            getattr(user, 'clan_land_speed_mastery_bonus', 0),
            force_max=getattr(user, 'fame_charles_invisible', False),
        )
        from app.repositories.title_repo import title_repo
        has_focus = await title_repo.has_title(session, user.id, "focus")
        extra = 20 if has_focus else 0
        recruit_cd = cooldown_service.apply_speed_reduction(5 * 60, speed_pct, extra)
        await cooldown_service.set_cooldown(cd_key, recruit_cd)

        return {
            "ok": True,
            "count": total_recruited,
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

        # Слава — Гапрена «Герой»: ×2 получение статистов из любых источников (в т.ч. магазин)
        granted = count * 2 if getattr(user, "fame_gaprena_hero", False) else count
        user.total_statists_recruited = (user.total_statists_recruited or 0) + granted

        # Один UPSERT независимо от количества — покупка миллионов статистов
        # больше не создаёт миллионы строк, просто прибавляет к счётчику группы.
        await squad_repo.add_count(session, user.id, rank, 0, granted, base_power=rank_cfg.base_power)
        await squad_repo.update_user_combat_power(session, user)

        return {"ok": True, "count": granted, "total_cost": total}

    # ════════════════════════════════════════════════════════════════════════
    # ТРЕНИРОВКА
    # ════════════════════════════════════════════════════════════════════════

    async def train(self, session: AsyncSession, user: User, bypass_cd: bool = False) -> dict:
        """
        Тренировка отряда.
        - Охват = TRAIN_BASE_COVERAGE + train_bonus_percent + prestige_train_bonus + зелье
        - Случайная выборка среди статистов с < 5 звёзд, пропорционально распределённая
          по группам (rank, stars, base_power) — не по отдельным бойцам
        - Каждая обученная единица получает от 1 до 3 звёзд (не превышая 5)
        - Шанс успеха: TRAIN_BASE_SUCCESS_CHANCE + train_quality_bonus (макс TRAIN_MAX_SUCCESS_CHANCE)

        bypass_cd — используется только Ультра Инстинктом при бонусе сета Гана
        «Истинный ультра инстинкт» (х2 тренировка за тик).
        """
        cd_key = cooldown_service.train_key(user.id)

        # double_train: проверяем вторую тренировку
        is_second = False
        if user.double_train:
            dkey = cooldown_service.double_train_key(user.id)
            if not await cooldown_service.is_on_cooldown(dkey):
                is_second = True

        if not is_second and not bypass_cd and await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"Тренировка через {cooldown_service.format_ttl(ttl)}"}

        # Группы-кандидаты (десятки строк максимум, не миллионы бойцов)
        groups = await squad_repo.get_groups(session, user.id)
        eligible = [g for g in groups if g.stars < 5 and g.count > 0]
        total_eligible = sum(g.count for g in eligible)
        if not total_eligible:
            return {"ok": False, "reason": "Все статисты уже имеют 5 звёзд или отряд пуст"}

        # Охват тренировки (% от кандидатов)
        train_bonus = await potion_service.get_effective_train_bonus(session, user)
        clan_train = getattr(user, 'clan_train_bonus', 0) + getattr(user, 'clan_donat_train_bonus', 0)
        coverage_pct = min(100, TRAIN_BASE_COVERAGE + train_bonus + clan_train)
        count_to_train = max(1, int(total_eligible * coverage_pct / 100))
        count_to_train = min(count_to_train, total_eligible)

        success_chance = min(TRAIN_MAX_SUCCESS_CHANCE, TRAIN_BASE_SUCCESS_CHANCE + user.train_quality_bonus)

        # Делим count_to_train между группами пропорционально их размеру, затем
        # в каждой группе O(1)-выборкой определяем сколько успело/провалилось
        # и как распределились +1/+2/+3 звезды — без построчной симуляции.
        group_alloc = largest_remainder_alloc(
            [((g.rank, g.stars, g.base_power), g.count) for g in eligible],
            count_to_train,
        )

        upgraded_total = 0
        stars_added_total = 0
        for g in eligible:
            k = group_alloc.get((g.rank, g.stars, g.base_power), 0)
            if k <= 0:
                continue
            successes = sample_binomial(k, success_chance / 100)
            if successes <= 0:
                continue
            d1, d2, d3 = split_three_way(successes)
            moved = 0
            for delta, cnt in ((1, d1), (2, d2), (3, d3)):
                if cnt <= 0:
                    continue
                new_stars = min(g.stars + delta, 5)
                await squad_repo.add_count(session, user.id, g.rank, new_stars, cnt, base_power=g.base_power)
                stars_added_total += cnt * (new_stars - g.stars)
                moved += cnt
            if moved:
                await squad_repo.add_count(session, user.id, g.rank, g.stars, -moved, base_power=g.base_power)
            upgraded_total += successes

        failed = count_to_train - upgraded_total

        await squad_repo.update_user_combat_power(session, user)

        # КД тренировки с учётом скорости и focus
        mastery = await _get_mastery(session, user.id)
        speed_pct = _get_speed_reduction(
            mastery, user.skill_path_bonus_multiplier,
            getattr(user, 'clan_land_speed_mastery_bonus', 0),
            force_max=getattr(user, 'fame_charles_invisible', False),
        )
        from app.repositories.title_repo import title_repo
        has_focus = await title_repo.has_title(session, user.id, "focus")
        extra = 20 if has_focus else 0
        clan_speed = (getattr(user, 'clan_train_bonus', 0) + getattr(user, 'clan_donat_train_bonus', 0)) // 2
        train_cd_seconds = cooldown_service.apply_speed_reduction(5 * 60, speed_pct, extra + clan_speed)

        if is_second:
            await cooldown_service.set_cooldown(
                cooldown_service.double_train_key(user.id), train_cd_seconds
            )
        else:
            await cooldown_service.set_cooldown(cd_key, train_cd_seconds)

        return {
            "ok": True,
            "trained": count_to_train,
            "upgraded": upgraded_total,
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
        groups = await squad_repo.get_groups(session, user_id)
        if not groups:
            return "Отряд пуст"

        rank_order = ["ERROR","DX","XXX","XX","X","MP","LR","UR","SSR","SR","SSS","SS","S","A","B","C","D","E","F"]

        rank_data: dict[str, dict[int, int]] = {}
        total = 0
        five_star = 0
        for g in groups:
            rank_data.setdefault(g.rank, {})[g.stars] = rank_data.get(g.rank, {}).get(g.stars, 0) + g.count
            total += g.count
            if g.stars == 5:
                five_star += g.count

        lines = []
        for rank in rank_order:
            star_counts = rank_data.get(rank)
            if not star_counts:
                continue
            rank_total = sum(star_counts.values())
            rank_cfg = RANKS_BY_ID.get(rank)
            star_parts = []
            for stars in range(5, -1, -1):
                c = star_counts.get(stars, 0)
                if c:
                    star_str = "⭐" * stars if stars > 0 else "☆"
                    star_parts.append(f"{star_str}×{c}")
            power_label = f"{rank_cfg.base_power:,} силы" if rank_cfg else "? силы"
            lines.append(
                f"[{rank}] {power_label} — {rank_total} чел.\n"
                f"  {' | '.join(star_parts)}"
            )

        lines.append(f"\n👥 Всего: {total} | ⭐×5: {five_star}")
        return "\n".join(lines)


squad_service = SquadService()
