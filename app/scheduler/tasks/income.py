"""
income_tick — оптимизированная версия для 5000+ игроков.

Было: загрузка 5000 ORM-объектов + N запросов зелий per-user + N flush'ей
      ≈ 10 000–15 000 запросов к БД каждую минуту.

Стало:
  1. SELECT только нужных колонок (6 полей вместо 110+)
  2. Один SELECT всех активных income-зелий (GROUP BY user_id)
  3. Python-расчёт дельт (O(n) в памяти, без БД)
  4. Один bulk UPDATE через unnest() для всех игроков сразу
  5. Один bulk UPDATE для учителей (реферальная система)
  ≈ 3–5 запросов к БД вместо 15 000.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select, text, func, or_
from app.database import AsyncSessionFactory
from app.models.user import User
from app.models.potion import ActivePotion

logger = logging.getLogger(__name__)


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

                if u.income_per_minute > 0:
                    potion_bonus = income_bonuses.get(u.id, 0)
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

                # Пассивный доход от круговых донатов: NHCoin/час → /60 за тик
                circ = u.circ_passive_income or 0
                if circ > 0:
                    per_tick = circ // 60
                    if per_tick > 0:
                        earned += per_tick

                if earned > 0:
                    user_deltas[u.id] = earned

            # ── 4. Bulk UPDATE игроков — один SQL вместо 5000 flush'ей ──────
            if user_deltas:
                ids = list(user_deltas.keys())
                deltas = [user_deltas[i] for i in ids]
                try:
                    await session.execute(
                        text("""
                            UPDATE users
                            SET nh_coins = users.nh_coins + d.delta
                            FROM unnest(:ids::int[], :deltas::bigint[]) AS d(uid, delta)
                            WHERE users.id = d.uid
                        """),
                        {"ids": ids, "deltas": deltas},
                    )
                except Exception as e:
                    logger.error(f"income_tick bulk update error: {e}")
                    raise

            # ── 5. Bulk UPDATE учителей (реферальная система) ────────────────
            if teacher_deltas:
                t_ids = list(teacher_deltas.keys())
                t_deltas = [teacher_deltas[i] for i in t_ids]
                try:
                    await session.execute(
                        text("""
                            UPDATE users
                            SET nh_coins = users.nh_coins + d.delta
                            FROM unnest(:ids::int[], :deltas::bigint[]) AS d(uid, delta)
                            WHERE users.id = d.uid
                        """),
                        {"ids": t_ids, "deltas": t_deltas},
                    )
                except Exception as e:
                    logger.error(f"income_tick teacher update error: {e}")
                    raise

            logger.debug(
                "income_tick: %d players updated, %d teachers credited",
                len(user_deltas),
                len(teacher_deltas),
            )
