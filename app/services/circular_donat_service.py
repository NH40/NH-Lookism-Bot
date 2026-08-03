"""
Сервис круговых донатов.

Логика:
  add_circle(session, user, donat_id) → добавляет 1 круг, применяет бонусы, обновляет user.*
  remove_circle(session, user, donat_id) → убирает 1 круг, пересчитывает всё с нуля
  rebuild_circular_bonuses(session, user) → полный пересчёт всех кругов для пользователя

Поля User, которые используют круговые донаты (не пересекаются с титульными сетами):
  squad_power_bonus        — складывается с титульными
  income_bonus_percent     — складывается с титульными
  recruit_count_bonus      — складывается с титульными
  all_cd_reduction         — складывается с титульными
  path_unique_1, path_unique_2 — могут выставляться кругами «Тень»
  circ_passive_income      — только круговые
  circ_defense_bonus       — только круговые
  fragment_bonus_pct       — только круговые
  circ_raid_bonus_pct      — только круговые
  circ_reflect_pct         — только круговые
  circ_ticket_overflow     — только круговые
  circ_instant_raid_chance — только круговые
  circ_double_raid_chance  — только круговые
  circ_daily_districts     — только круговые
  circ_dragon_active       — только круговые
  circ_clan_cashback       — только круговые
  circ_clan_income_skim_pct — только круговые
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.circular_donat import UserCircularDonat
from app.data.titles import CIRCULAR_DONAT_MAP


# Поля, которые круговые донаты добавляют к уже-выставленным титульным бонусам.
# При rebuild_circular_bonuses мы НЕ обнуляем эти поля целиком — вместо этого
# используем отдельные «circ_delta» счётчики и добавляем дельту поверх того,
# что выставили титулы.  Для упрощения: rebuild вызывается ПОСЛЕ reapply_all_titles,
# поэтому «фон» от титулов уже лежит в полях, и мы просто добавляем сумму кругов.

_CIRC_ONLY_FIELDS = (
    "circ_passive_income",
    "circ_defense_bonus",
    "fragment_bonus_pct",
    "circ_raid_bonus_pct",
    "circ_reflect_pct",
    "circ_ticket_overflow",
    "circ_instant_raid_chance",
    "circ_double_raid_chance",
    "circ_daily_districts",
    "circ_dragon_active",
    "circ_clan_cashback",
    "circ_clan_income_skim_pct",
    # path_unique_1 и path_unique_2 тоже только от кругов (не от титулов)
    "path_unique_1",
    "path_unique_2",
)

# Поля, которые СКЛАДЫВАЮТСЯ с titlр-бонусами.
# Чтобы знать, какую дельту добавили круги, мы их пересчитываем с нуля
# и прибавляем поверх текущего значения (которое уже включает титулы).
# Поэтому rebuild_circular_bonuses должен вызываться в самом конце.

_ADDITIVE_FIELDS = (
    "squad_power_bonus",
    "income_bonus_percent",
    "recruit_count_bonus",
    "all_cd_reduction",
    "influence_bonus_percent",
)


def _apply_one_donat(user: User, donat_id: str, circles: int) -> None:
    """Применяет бонус одного кругового доната (circles кругов) к пользователю.
    Вызывается с уже-ОБНУЛЁННЫМИ circ-полями, но сохранёнными additive-полями от титулов."""
    if circles <= 0:
        return

    if donat_id == "archangel":
        user.squad_power_bonus += 30 * circles
        user.income_bonus_percent += 50 * circles
        user.circ_passive_income += 500 * circles
        if circles >= 3:
            user.circ_raid_bonus_pct += 10
        if circles >= 5:
            user.circ_reflect_pct += 3
        if circles >= 10:
            user.circ_daily_districts = max(user.circ_daily_districts, 64)

    elif donat_id == "clan_head":
        # Личная часть (сверх клан-вайд трансляции — см. _broadcast_clan_head).
        # Клан-вайд +5% сила/доход/вербовка/влияние всем членам клана — отдельно.
        user.squad_power_bonus += 10 * circles
        user.influence_bonus_percent += 5 * circles
        if circles >= 3:
            user.circ_clan_income_skim_pct = 10
        if circles >= 5:
            user.circ_clan_cashback = True

    elif donat_id == "korea_devil":
        user.squad_power_bonus += 10 * circles
        user.influence_bonus_percent += 10 * circles
        user.circ_passive_income += 300 * circles
        if circles >= 3:
            user.circ_instant_raid_chance += 5
        if circles >= 6:
            user.circ_double_raid_chance += 5

    elif donat_id == "mountain_lord":
        user.squad_power_bonus += 20 * circles
        user.influence_bonus_percent += 10 * circles
        if circles >= 2:
            user.circ_mountain_extra = True
        if circles >= 4:
            user.circ_ticket_overflow = True

    elif donat_id == "shadow":
        user.all_cd_reduction += 1 * circles
        if circles >= 3:
            user.path_unique_1 = True
        if circles >= 5:
            user.path_unique_2 = True

    elif donat_id == "dragon":
        user.squad_power_bonus += 10 * circles
        if circles >= 3:
            user.circ_defense_bonus += 10
        if circles >= 6:
            user.circ_dragon_active = True

    elif donat_id == "dungeon_lord":
        user.circ_passive_income += 1000 * circles
        user.fragment_bonus_pct += 5 * circles
        if circles >= 2:
            user.fragment_bonus_pct += 10
        if circles >= 4:
            user.fragment_bonus_pct += 10
        user.train_bonus_percent += 5 * circles

    elif donat_id == "emperor_circle":
        # Базовые бонусы за круг (income был задвоен двумя полями — правили
        # по прямому запросу владельца проекта: должно быть ровно +5%/круг)
        base_power_per = 20
        base_income_per = 5
        base_influence_per = 10
        base_passive_per = 400
        base_recruit_per = 30

        # Stack bonus: +5% to following bonuses at circles 3, 5, 10
        stack = 0
        for threshold in (3, 5, 10):
            if circles >= threshold:
                stack += 5  # each milestone adds +5% to the per-circle multipliers
        multiplier = 1.0 + stack / 100.0

        user.squad_power_bonus += int(base_power_per * circles * multiplier)
        user.income_bonus_percent += int(base_income_per * circles * multiplier)
        user.influence_bonus_percent += int(base_influence_per * circles * multiplier)
        user.circ_passive_income += int(base_passive_per * circles * multiplier)
        user.recruit_count_bonus += int(base_recruit_per * circles * multiplier)
        user.circ_trainer_discount += int(2 * circles * multiplier)


async def rebuild_circular_bonuses(session: AsyncSession, user: User) -> None:
    """
    Полный пересчёт всех кругов.
    Вызывать ПОСЛЕ reapply_all_titles — только добавляет дельту сверху.

    Алгоритм:
    1. Обнуляем только circ-only поля (path_unique_* оставляем, если были от пути).
    2. Запрашиваем все записи UserCircularDonat для пользователя.
    3. Для каждого доната вызываем _apply_one_donat.
    4. flush.
    """
    # Сбросить circ-only поля
    user.circ_passive_income = 0
    user.circ_defense_bonus = 0
    user.fragment_bonus_pct = 0
    user.circ_raid_bonus_pct = 0
    user.circ_reflect_pct = 0
    user.circ_ticket_overflow = False
    user.circ_instant_raid_chance = 0
    user.circ_double_raid_chance = 0
    user.circ_daily_districts = 0
    user.circ_dragon_active = False
    user.circ_clan_cashback = False
    user.circ_clan_income_skim_pct = 0
    user.circ_mountain_extra = False
    user.circ_trainer_discount = 0
    # path_unique_1/2 НЕ сбрасываем здесь: rebuild_base_bonuses (вызывается
    # раньше, в reapply_all_titles) уже мог выставить их из купленных скиллов
    # Пути (Тень: "первый удар"/"невидимость") — круги доната "Тень" ниже
    # могут только ДОБАВИТЬ True поверх, а не затирать то, что дали скиллы.
    # Раньше это был баг: игрок с прокачанным скиллом, но <3/<5 кругов "Тень",
    # терял бонус при каждом reapply_all_titles (любая смена титулов).

    rows = await session.execute(
        select(UserCircularDonat).where(UserCircularDonat.user_id == user.id)
    )
    records = rows.scalars().all()
    for rec in records:
        _apply_one_donat(user, rec.donat_id, rec.circles)

    await session.flush()


async def add_circle(session: AsyncSession, user: User, donat_id: str) -> dict:
    """Добавить 1 круг игроку. Возвращает {'ok': True/False, 'circles': n}."""
    cfg = CIRCULAR_DONAT_MAP.get(donat_id)
    if not cfg:
        return {"ok": False, "reason": "Донат не найден"}

    rec = await session.scalar(
        select(UserCircularDonat).where(
            UserCircularDonat.user_id == user.id,
            UserCircularDonat.donat_id == donat_id,
        )
    )
    if rec is None:
        rec = UserCircularDonat(user_id=user.id, donat_id=donat_id, circles=0)
        session.add(rec)
        await session.flush()

    if rec.circles >= cfg.max_circles:
        return {"ok": False, "reason": f"Достигнут максимум {cfg.max_circles} кругов"}

    rec.circles += 1
    await session.flush()

    # Полный пересчёт бонусов (чтобы не было дублирования)
    await _full_rebuild(session, user)
    if donat_id == "clan_head":
        await _broadcast_clan_head(session, user)
    return {"ok": True, "circles": rec.circles}


async def remove_circle(session: AsyncSession, user: User, donat_id: str) -> dict:
    """Убрать 1 круг. Возвращает {'ok': True/False, 'circles': n}."""
    rec = await session.scalar(
        select(UserCircularDonat).where(
            UserCircularDonat.user_id == user.id,
            UserCircularDonat.donat_id == donat_id,
        )
    )
    if rec is None or rec.circles <= 0:
        return {"ok": False, "reason": "Кругов нет"}

    rec.circles -= 1
    await session.flush()

    await _full_rebuild(session, user)
    if donat_id == "clan_head":
        await _broadcast_clan_head(session, user)
    return {"ok": True, "circles": rec.circles}


async def get_user_circles(session: AsyncSession, user_id: int) -> dict[str, int]:
    """Возвращает {donat_id: circles} для пользователя."""
    rows = await session.execute(
        select(UserCircularDonat).where(
            UserCircularDonat.user_id == user_id,
            UserCircularDonat.circles > 0,
        )
    )
    return {r.donat_id: r.circles for r in rows.scalars().all()}


async def _broadcast_clan_head(session: AsyncSession, user: User) -> None:
    """Клан-вайд часть доната "Глава клана" — вызывается при add/remove_circle
    покупателем, у которого точно есть клан на момент вызова."""
    from app.services.clan import clan_service
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        return
    await recalc_clan_head_bonus(session, clan.id)


async def recalc_clan_head_bonus(session: AsyncSession, clan_id: int) -> None:
    """Клан-вайд часть доната "Глава клана": суммирует круги этого доната
    у ВСЕХ ТЕКУЩИХ участников клана и транслирует +5%/круг силы/дохода/
    вербовки/влияния каждому члену клана. Публичная — вызывается и отсюда
    (после add/remove круга), и из clan/base.py (после ухода/исключения
    участника — состав клана уже изменился к моменту вызова)."""
    from app.models.clan import Clan, ClanMember
    from app.services.business_service import business_service
    from app.repositories.squad_repo import squad_repo

    clan = await session.get(Clan, clan_id)
    if not clan:
        return

    member_ids = (await session.execute(
        select(ClanMember.user_id).where(ClanMember.clan_id == clan.id)
    )).scalars().all()
    if not member_ids:
        clan.head_power_pct = 0
        clan.head_income_pct = 0
        clan.head_recruit_pct = 0
        clan.head_influence_pct = 0
        await session.flush()
        return

    rows = (await session.execute(
        select(UserCircularDonat.circles).where(
            UserCircularDonat.user_id.in_(member_ids),
            UserCircularDonat.donat_id == "clan_head",
        )
    )).scalars().all()
    total_circles = sum(rows)

    clan.head_power_pct = 5 * total_circles
    clan.head_income_pct = 5 * total_circles
    clan.head_recruit_pct = 5 * total_circles
    clan.head_influence_pct = 5 * total_circles
    await session.flush()

    members = (await session.execute(
        select(User).where(User.id.in_(member_ids))
    )).scalars().all()
    for m in members:
        m.clan_head_power_bonus = clan.head_power_pct
        m.clan_head_income_bonus = clan.head_income_pct
        m.clan_head_recruit_bonus = clan.head_recruit_pct
        m.clan_head_influence_bonus = clan.head_influence_pct
        await business_service._recalc_income(session, m)
        await squad_repo.update_user_combat_power(session, m)
    await session.flush()


async def _full_rebuild(session: AsyncSession, user: User) -> None:
    """Пересчитывает и титулы, и круговые бонусы.
    reapply_all_titles уже вызывает rebuild_circular_bonuses внутри,
    поэтому здесь достаточно одного вызова."""
    from app.services.title_service import title_service
    # reapply_all_titles → rebuild_circular_bonuses → _recalc_income → update_combat_power
    await title_service.reapply_all_titles(session, user)
