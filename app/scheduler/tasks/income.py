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
import logging
from datetime import datetime, timezone

from sqlalchemy import select, text, func, or_
from app.database import AsyncSessionFactory
from app.models.user import User
from app.models.potion import ActivePotion

logger = logging.getLogger(__name__)


def _bulk_update_sql(deltas: dict[int, int]) -> str:
    """
    Генерирует SQL с VALUES для bulk UPDATE.
    Все значения — целые числа, SQL-инъекция невозможна.
    Пример: UPDATE users SET nh_coins = nh_coins + v.delta
            FROM (VALUES (1,100),(2,200)) AS v(uid,delta)
            WHERE users.id = v.uid
    """
    rows = ", ".join(f"({int(uid)}, {int(delta)})" for uid, delta in deltas.items())
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
                    User.circ_passive_income,
                    User.referred_by,
                    User.teacher_income_share,
                    User.income_bonus_percent,
                    User.prestige_income_bonus,
                    User.clan_income_bonus,
                    User.clan_donat_income_bonus,
                ).where(
                    or_(User.income_per_minute > 0, User.circ_passive_income > 0)
                )
            )
            users = result.all()

            if not users:
                return

            user_ids = [u.id for u in users]

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
            user_deltas: dict[int, int] = {}    # user_id -> монеты к зачислению
            teacher_deltas: dict[int, int] = {} # teacher_id -> монеты к зачислению

            for u in users:
                earned = 0
                potion_bonus = income_bonuses.get(u.id, 0)

                if u.income_per_minute > 0:
                    total = int(u.income_per_minute * (1 + potion_bonus / 100))

                    if total > 0:
                        if u.referred_by:
                            share_pct = u.teacher_income_share or 3
                            teacher_share = max(1, int(total * share_pct / 100))
                            earned += total - teacher_share
                            teacher_deltas[u.referred_by] = (
                                teacher_deltas.get(u.referred_by, 0) + teacher_share
                            )
                        else:
                            earned += total

                # Пассивный доход от круговых донатов: NHCoin/мин (уже за минуту)
                # Применяем все % баффы дохода: навыки, пробуждение, клан, зелье
                circ = u.circ_passive_income or 0
                if circ > 0:
                    skills_bonus = (u.income_bonus_percent or 0) + (u.prestige_income_bonus or 0)
                    clan_bonus   = (u.clan_income_bonus or 0) + (u.clan_donat_income_bonus or 0)
                    circ_total_bonus = skills_bonus + clan_bonus + potion_bonus
                    per_tick = max(0, int(circ * (1 + circ_total_bonus / 100)))
                    if per_tick > 0:
                        earned += per_tick

                if earned > 0:
                    user_deltas[u.id] = earned

            # ── 4. Bulk UPDATE игроков — один SQL через VALUES ───────────────
            # VALUES безопасен: все значения явно приводятся к int выше
            if user_deltas:
                try:
                    await session.execute(text(_bulk_update_sql(user_deltas)))
                except Exception as e:
                    logger.error(f"income_tick bulk update error: {e}")
                    raise

            # ── 5. Bulk UPDATE учителей (реферальная система) ────────────────
            if teacher_deltas:
                try:
                    await session.execute(text(_bulk_update_sql(teacher_deltas)))
                except Exception as e:
                    logger.error(f"income_tick teacher update error: {e}")
                    raise

            logger.debug(
                "income_tick: %d players updated, %d teachers credited",
                len(user_deltas),
                len(teacher_deltas),
            )

    # ── 6. Трекинг квестов «доход» (отдельная сессия, не тормозит основной тик) ──
    if user_deltas:
        await _track_income_quests(user_deltas)


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

    # VALUES (uid, delta) — целые числа, SQL-инъекция невозможна
    rows = ", ".join(f"({int(uid)}, {int(d)})" for uid, d in active_deltas.items())

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
