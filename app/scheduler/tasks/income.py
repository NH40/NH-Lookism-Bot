"""
income_tick — оптимизированная версия для 5000+ игроков.

Примечание по трекингу квестов:
  Квесты «доход» (progress_key="income") обновляются в отдельной лёгкой сессии
  через прямой SQL-апдейт, чтобы не нарушать оптимизацию основного тика.


Было: загрузка 5000 ORM-объектов + N запросов зелий per-user + N flush'ей
      ≈ 10 000–15 000 запросов к БД каждую минуту.

Стало:
  1. SELECT только нужных колонок (6 полей вместо 110+)
  2. Один SELECT всех активных income-зелий (GROUP BY user_id)
  3. Python-расчёт дельт (O(n) в памяти, без БД)
  4. Один bulk UPDATE через VALUES для всех игроков сразу
  5. Один bulk UPDATE для учителей (реферальная система)
  ≈ 3–5 запросов к БД вместо 15 000.

Примечание по синтаксису:
  asyncpg не поддерживает ':param::type[]' в text() — парсер параметров
  SQLAlchemy конфликтует с оператором каста '::'.
  Решение: VALUES с интерполяцией целых чисел (SQL-инъекция невозможна —
  все значения проверены как int до вставки).
"""
import asyncio
import logging
import random
from datetime import datetime, timezone

from sqlalchemy import select, text, func, or_
from app.database import AsyncSessionFactory
from app.models.user import User
from app.models.potion import ActivePotion
from app.services.fame_service import fame_service
from app.config.game_balance import (
    ILLEGAL_INCOME_VOLATILITY_MIN, ILLEGAL_INCOME_VOLATILITY_MAX,
    VASSAL_TRIBUTE_PERCENT,
)

logger = logging.getLogger(__name__)


def _bulk_update_sql(deltas: dict[int, int]) -> str:
    """
    Генерирует SQL с VALUES для bulk UPDATE.
    Все значения — целые числа, SQL-инъекция невозможна.
    Пример: UPDATE users SET nh_coins = nh_coins + v.delta
            FROM (VALUES (1,100),(2,200)) AS v(uid,delta)
            WHERE users.id = v.uid

    Строки VALUES отсортированы по uid — Postgres блокирует затрагиваемые
    строки users примерно в этом порядке. Без сортировки порядок блокировок
    произвольный (порядок Python dict) и может отличаться от порядка,
    в котором обычные одиночные UPDATE users SET ... WHERE id=X (покупки,
    награды и т.д.) берут блокировку на то же множество строк — при
    пересечении это даёт "deadlock detected" под нагрузкой (падало в проде).
    """
    rows = ", ".join(
        f"({int(uid)}, {int(delta)})" for uid, delta in sorted(deltas.items())
    )
    return f"""
        UPDATE users
        SET nh_coins = users.nh_coins + v.delta
        FROM (VALUES {rows}) AS v(uid, delta)
        WHERE users.id = v.uid
    """


async def income_tick():
    async with AsyncSessionFactory() as session:
        async with session.begin():
            now = datetime.now(timezone.utc)

            # ── 1. Загружаем только нужные колонки ──────────────────────────
            result = await session.execute(
                select(
                    User.id,
                    User.income_per_minute,
                    User.business_path,
                    User.circ_passive_income,
                    User.referred_by,
                    User.teacher_income_share,
                    User.income_bonus_percent,
                    User.prestige_income_bonus,
                    User.clan_income_bonus,
                    User.clan_donat_income_bonus,
                    User.clan_land_income_pct,
                    User.title_casino_jackpot,
                    User.title_casino_blackjack,
                    User.fame_set_gaprena,
                    User.suzerain_id,
                    User.city_tax_percent,
                    User.city_tax_recipient_id,
                ).where(
                    or_(User.income_per_minute > 0, User.circ_passive_income > 0)
                )
            )
            users = result.all()

            if not users:
                return

            user_ids = [u.id for u in users]

            # ── 1b. Скимминг "Глава клана" (круг ≥3): владелец кругов получает
            # доп. % от дохода КАЖДОГО члена своего клана поверх их обычного
            # начисления — доход самих членов клана при этом не уменьшается.
            from app.models.clan import ClanMember

            skim_buyers = (await session.execute(
                select(User.id, User.circ_clan_income_skim_pct).where(
                    User.circ_clan_income_skim_pct > 0
                )
            )).all()
            clan_skim_members: dict[int, list[int]] = {}
            buyer_clan_pct: list[tuple[int, int, int]] = []
            if skim_buyers:
                buyer_ids = [b.id for b in skim_buyers]
                buyer_clan_map = dict((await session.execute(
                    select(ClanMember.user_id, ClanMember.clan_id).where(
                        ClanMember.user_id.in_(buyer_ids)
                    )
                )).all())
                relevant_clan_ids = list(set(buyer_clan_map.values()))
                if relevant_clan_ids:
                    for clan_id, uid in (await session.execute(
                        select(ClanMember.clan_id, ClanMember.user_id).where(
                            ClanMember.clan_id.in_(relevant_clan_ids)
                        )
                    )).all():
                        clan_skim_members.setdefault(clan_id, []).append(uid)
                    for b in skim_buyers:
                        clan_id = buyer_clan_map.get(b.id)
                        if clan_id is not None:
                            buyer_clan_pct.append((b.id, clan_id, b.circ_clan_income_skim_pct))

            # ── 2. Один запрос: сумма income-бонусов от зелий per user ──────
            pot_result = await session.execute(
                select(
                    ActivePotion.user_id,
                    func.sum(ActivePotion.bonus_value).label("total_bonus"),
                ).where(
                    ActivePotion.potion_type == "income",
                    ActivePotion.expires_at > now,
                    ActivePotion.user_id.in_(user_ids),
                ).group_by(ActivePotion.user_id)
            )
            income_bonuses: dict[int, int] = {
                row.user_id: row.total_bonus for row in pot_result.all()
            }

            # ── 3. Считаем дельты в Python ──────────────────────────────────
            # Один общий net_deltas на ВСЕХ получателей (сам игрок + учитель +
            # городской налог + вассальная дань) — единый bulk UPDATE вместо
            # нескольких, чтобы не плодить разнопорядковые блокировки одних и
            # тех же строк users в рамках одной транзакции (см. _bulk_update_sql).
            net_deltas: dict[int, int] = {}
            quest_deltas: dict[int, int] = {}  # трекинг квестов — ДО вычета налога/дани (эффорт, не чистый доход)
            member_net_income: dict[int, int] = {}  # фактически начисленный бизнес-доход (для скимминга "Глава клана")

            for u in users:
                potion_bonus = income_bonuses.get(u.id, 0)

                # Игровые титулы за рейтинг казино + бафф сета «Преодоление» (Слава — Гапрена)
                title_mult = 1.0
                if u.title_casino_jackpot:
                    title_mult *= 2.0
                if u.title_casino_blackjack:
                    title_mult *= 60 / 45  # эквивалент тика раз в 45с вместо 60с
                if u.fame_set_gaprena:
                    overcome_pct = await fame_service.get_overcome_bonus_pct(u.id)
                    if overcome_pct > 0:
                        title_mult *= 1 + overcome_pct / 100

                if u.income_per_minute > 0:
                    volatility_mult = 1.0
                    if u.business_path == "illegal":
                        volatility_mult = random.uniform(ILLEGAL_INCOME_VOLATILITY_MIN, ILLEGAL_INCOME_VOLATILITY_MAX)
                    total = int(u.income_per_minute * (1 + potion_bonus / 100) * title_mult * volatility_mult)

                    if total > 0:
                        quest_deltas[u.id] = quest_deltas.get(u.id, 0) + total
                        remaining = total

                        # Городской налог — королю города, если чужой
                        if u.city_tax_percent and u.city_tax_recipient_id:
                            tax_amt = int(remaining * u.city_tax_percent / 100)
                            if tax_amt > 0:
                                remaining -= tax_amt
                                net_deltas[u.city_tax_recipient_id] = (
                                    net_deltas.get(u.city_tax_recipient_id, 0) + tax_amt
                                )

                        # Вассальная дань — сюзерену
                        if u.suzerain_id:
                            tribute_amt = int(remaining * VASSAL_TRIBUTE_PERCENT / 100)
                            if tribute_amt > 0:
                                remaining -= tribute_amt
                                net_deltas[u.suzerain_id] = (
                                    net_deltas.get(u.suzerain_id, 0) + tribute_amt
                                )

                        # Учительская доля (реферальная система)
                        if u.referred_by:
                            share_pct = u.teacher_income_share or 3
                            teacher_share = max(1, int(remaining * share_pct / 100))
                            remaining -= teacher_share
                            net_deltas[u.referred_by] = net_deltas.get(u.referred_by, 0) + teacher_share

                        net_deltas[u.id] = net_deltas.get(u.id, 0) + remaining
                        member_net_income[u.id] = remaining

                # Пассивный доход: circ-донаты (налог/дань не затрагивают — отдельный источник)
                circ = u.circ_passive_income or 0
                if circ > 0:
                    skills_bonus = (u.income_bonus_percent or 0) + (u.prestige_income_bonus or 0)
                    clan_bonus   = (u.clan_income_bonus or 0) + (u.clan_donat_income_bonus or 0) + (u.clan_land_income_pct or 0)
                    circ_total_bonus = skills_bonus + clan_bonus + potion_bonus
                    per_tick = max(0, int(circ * (1 + circ_total_bonus / 100) * title_mult))
                    if per_tick > 0:
                        net_deltas[u.id] = net_deltas.get(u.id, 0) + per_tick

            # ── 3b. Скимминг "Глава клана": владелец кругов получает % от
            # фактического дохода каждого члена клана ДОПОЛНИТЕЛЬНО, поверх
            # net_deltas — доход самих членов клана не уменьшается.
            for buyer_id, clan_id, pct in buyer_clan_pct:
                member_ids = clan_skim_members.get(clan_id, [])
                total_members_income = sum(member_net_income.get(mid, 0) for mid in member_ids)
                skim_amt = int(total_members_income * pct / 100)
                if skim_amt > 0:
                    net_deltas[buyer_id] = net_deltas.get(buyer_id, 0) + skim_amt

            # ── 4. Bulk UPDATE — один SQL через VALUES ────────────────────────
            # VALUES безопасен: все значения явно приводятся к int выше
            if net_deltas:
                try:
                    await session.execute(text(_bulk_update_sql(net_deltas)))
                except Exception as e:
                    logger.error(f"income_tick bulk update error: {e}")
                    raise

            logger.debug(
                "income_tick: %d получателей обновлено", len(net_deltas),
            )

    # ── 5. Трекинг квестов «доход» — fire-and-forget, не блокирует тик ──
    if quest_deltas:
        asyncio.create_task(_track_income_quests(quest_deltas))


async def _track_income_quests(user_deltas: dict[int, int]) -> None:
    """
    Обновляет прогресс ежедневных квестов с progress_key='income'.
    Один bulk UPDATE на тип квеста вместо N запросов per-user.
    """
    from app.constants.quests import QUESTS_BY_ID
    from datetime import date

    today = date.today().isoformat()

    income_quest_ids = [
        q.quest_id for q in QUESTS_BY_ID.values()
        if (q.progress_key or q.quest_id) == "income"
    ]
    if not income_quest_ids:
        return

    active_deltas = {uid: d for uid, d in user_deltas.items() if d > 0}
    if not active_deltas:
        return

    # VALUES (uid, delta) — целые числа, SQL-инъекция невозможна.
    # Сортировка по uid — тот же приём против дедлоков, см. _bulk_update_sql.
    rows = ", ".join(f"({int(uid)}, {int(d)})" for uid, d in sorted(active_deltas.items()))

    try:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                for quest_id in income_quest_ids:
                    target = int(QUESTS_BY_ID[quest_id].target)
                    await session.execute(text(f"""
                        UPDATE daily_quests dq
                        SET
                            progress = LEAST(dq.progress + v.delta, {target}),
                            is_completed = CASE
                                WHEN LEAST(dq.progress + v.delta, {target}) >= {target} THEN TRUE
                                ELSE dq.is_completed
                            END
                        FROM (VALUES {rows}) AS v(uid, delta)
                        WHERE dq.user_id = v.uid
                          AND dq.date = :today
                          AND dq.quest_id = :qid
                          AND dq.is_completed = FALSE
                    """), {"today": today, "qid": quest_id})
    except Exception as exc:
        logger.warning(f"_track_income_quests error: {exc}")
