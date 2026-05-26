"""
Фоновые задачи банка:
  bank_credit_tick  — каждую минуту: блокировки, снос банд, уведомления
  crypto_price_tick — каждые 5 минут: обновление курсов
  storage_fee_tick  — каждую минуту: плата за ячейки
  investment_tick   — каждую минуту: уведомления о созревших вкладах
"""
import logging
from app.database import AsyncSessionFactory

logger = logging.getLogger(__name__)


# ─── Кредиты ─────────────────────────────────────────────────────────────────

async def bank_credit_tick():
    """
    Проверяет все активные кредиты:
    - Если просрочен 3ч и нет уведомления — отправить сообщение-блокировку
    - Если просрочен 6ч — снести банду игрока и пометить кредит
    """
    from datetime import datetime, timezone
    from sqlalchemy import select, and_
    from app.models.bank import BankCredit
    from app.models.user import User as UserModel

    async with AsyncSessionFactory() as session:
        async with session.begin():
            now = datetime.now(timezone.utc)

            # Кредиты для блокировки (3ч истекло, но уведомление ещё не отправлено)
            block_r = await session.execute(
                select(BankCredit).where(
                    and_(
                        BankCredit.is_paid == False,
                        BankCredit.block_at <= now,
                        BankCredit.notif_block_sent == False,
                    )
                )
            )
            to_block = block_r.scalars().all()

            bot_instance = None
            if to_block:
                try:
                    from app.bot_instance import get_bot
                    bot_instance = get_bot()
                except Exception:
                    pass

            blocked_user_ids = set()
            for credit in to_block:
                credit.notif_block_sent = True
                blocked_user_ids.add(credit.user_id)

            if blocked_user_ids and bot_instance:
                users_r = await session.execute(
                    select(UserModel).where(UserModel.id.in_(blocked_user_ids))
                )
                for u in users_r.scalars().all():
                    try:
                        from app.utils.formatters import fmt_num
                        # Считаем общий долг
                        debts_r = await session.execute(
                            select(BankCredit).where(
                                and_(BankCredit.user_id == u.id, BankCredit.is_paid == False)
                            )
                        )
                        debts = debts_r.scalars().all()
                        total_debt = sum(c.due_amount - c.paid_amount for c in debts)
                        await bot_instance.send_message(
                            u.tg_id,
                            f"🚫 <b>Кредит просрочен!</b>\n\n"
                            f"Общий долг: <b>{fmt_num(total_debt)} NHCoin</b>\n\n"
                            f"⚠️ Тренировки, атаки и рейды заблокированы!\n"
                            f"Погасите долг в <b>Банк → Кредиты</b>.\n\n"
                            f"⏰ Через 3 часа банда будет <b>удалена</b>!",
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        logger.warning(f"credit block notif error for user {u.id}: {e}")

            # Кредиты для сноса банды (6ч истекло)
            delete_r = await session.execute(
                select(BankCredit).where(
                    and_(
                        BankCredit.is_paid == False,
                        BankCredit.is_gang_deleted == False,
                        BankCredit.delete_at <= now,
                    )
                )
            )
            to_delete = delete_r.scalars().all()
            delete_user_ids = set(c.user_id for c in to_delete)

            if delete_user_ids:
                users_r = await session.execute(
                    select(UserModel).where(UserModel.id.in_(delete_user_ids))
                )
                users_map = {u.id: u for u in users_r.scalars().all()}

                for credit in to_delete:
                    credit.is_gang_deleted = True
                    credit.notif_delete_sent = True
                    u = users_map.get(credit.user_id)
                    if not u:
                        continue
                    # Снос банды: сбрасываем название и привязку к городу
                    if u.gang_name:
                        old_name = u.gang_name
                        u.gang_name = None
                        u.gang_city_id = None
                        u.sector = None
                        # Не сбрасываем nh_coins, phase, прочее — только банду

                        # Уведомление
                        if bot_instance:
                            try:
                                from app.utils.formatters import fmt_num
                                remaining = credit.due_amount - credit.paid_amount
                                await bot_instance.send_message(
                                    u.tg_id,
                                    f"💀 <b>Банда удалена за долги!</b>\n\n"
                                    f'Ваша банда "<b>{old_name}</b>" удалена.\n'
                                    f"Долг: <b>{fmt_num(remaining)} NHCoin</b>\n\n"
                                    f"Кредит всё ещё активен! Выплатите его в Банке,\n"
                                    f"чтобы создать новую банду.",
                                    parse_mode="HTML",
                                )
                            except Exception as e:
                                logger.warning(f"credit delete notif error for user {u.id}: {e}")


# ─── Крипто цены ─────────────────────────────────────────────────────────────

async def crypto_price_tick():
    """Обновить курсы всех криптовалют."""
    async with AsyncSessionFactory() as session:
        async with session.begin():
            try:
                from app.services.bank.crypto_service import crypto_service
                await crypto_service.price_tick(session)
            except Exception as e:
                logger.error(f"crypto_price_tick error: {e}")


# ─── Плата за хранилище ───────────────────────────────────────────────────────

async def storage_fee_tick():
    """Снять ежеминутную плату за непустые ячейки хранилища."""
    async with AsyncSessionFactory() as session:
        async with session.begin():
            try:
                from app.services.bank.storage_service import storage_service
                await storage_service.fee_tick(session)
            except Exception as e:
                logger.error(f"storage_fee_tick error: {e}")


# ─── Инвестиции ───────────────────────────────────────────────────────────────

async def investment_tick():
    """Пометить созревшие вклады и уведомить игроков."""
    async with AsyncSessionFactory() as session:
        async with session.begin():
            try:
                from app.services.bank.investments_service import investments_service
                matured = await investments_service.maturity_tick(session)

                if not matured:
                    return

                from sqlalchemy import select
                from app.models.user import User as UserModel
                user_ids = [inv.user_id for inv in matured]
                users_r = await session.execute(
                    select(UserModel).where(UserModel.id.in_(user_ids))
                )
                users_map = {u.id: u for u in users_r.scalars().all()}

                try:
                    from app.bot_instance import get_bot
                    bot_instance = get_bot()
                except Exception:
                    bot_instance = None

                if not bot_instance:
                    return

                from app.utils.formatters import fmt_num
                for inv in matured:
                    u = users_map.get(inv.user_id)
                    if not u:
                        continue
                    payout = inv.amount + int(inv.amount * inv.interest_pct / 100)
                    try:
                        await bot_instance.send_message(
                            u.tg_id,
                            f"📈 <b>Вклад созрел!</b>\n\n"
                            f"Сумма: {fmt_num(inv.amount)} NHCoin\n"
                            f"Прибыль: +{inv.interest_pct}%\n"
                            f"К получению: <b>{fmt_num(payout)} NHCoin</b>\n\n"
                            f"Забери деньги в <b>Банк → Инвестиции</b>!",
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        logger.warning(f"investment notif error for user {u.id}: {e}")
            except Exception as e:
                logger.error(f"investment_tick error: {e}")
