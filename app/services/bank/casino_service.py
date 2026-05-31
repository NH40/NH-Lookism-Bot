"""
Казино: ставки на ресурсы с детектором стратегии x3.
Казино всегда побеждает — у игрока лишь 30% шанс выиграть 2× ставки.
"""
import random
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User

from app.constants.bank import (
    CASINO_WIN_CHANCE, CASINO_WIN_MULTIPLIER,
    CASINO_HISTORY_TTL, CASINO_X3_RATIO_MIN, CASINO_X3_RATIO_MAX,
)

logger = logging.getLogger(__name__)

# ── Допустимые ресурсы ────────────────────────────────────────────────────────
CASINO_RESOURCES: dict[str, str] = {
    "nh_coins":           "💰 NHCoin",
    "tickets":            "🎟 Тикеты",
    "card_dust":          "🌫 Пыль карт",
    "ui_fragments":       "🔮 Фрагменты УИ",
    "alchemy_fragments":  "🧪 Фрагменты алхимии",
    "path_fragments":     "🩺 Фрагменты пути",
    "business_fragments": "🏢 Фрагменты бизнеса",
    "war_points":         "⚔️ Очки войны",
    "mastery_points":     "🎯 Очки мастерства",
}
CASINO_RESOURCE_LABELS = CASINO_RESOURCES  # алиас

WIN_CHANCE     = CASINO_WIN_CHANCE
WIN_MULTIPLIER = CASINO_WIN_MULTIPLIER

# Детектор стратегии x3: храним 3 последних ставки в Redis
_HISTORY_KEY = "casino:bets:{uid}:{res}"
_HISTORY_TTL = CASINO_HISTORY_TTL


class CasinoService:

    def _redis(self):
        from app.services.cooldown_service import cooldown_service
        return cooldown_service.redis

    # ── Получить текущий запас ресурса ────────────────────────────────────────

    def get_balance(self, user: User, resource: str) -> int:
        return getattr(user, resource, 0)

    def set_balance(self, user: User, resource: str, value: int) -> None:
        setattr(user, resource, value)

    # ── Детектор x3 ──────────────────────────────────────────────────────────

    async def _detect_x3(self, user_id: int, resource: str, amount: int) -> bool:
        """
        Возвращает True если ставка является частью паттерна x3 (3 подряд).
        Паттерн: ставка[i] ≈ 3 × ставка[i-1] (±10% допуск).
        """
        redis = self._redis()
        key = _HISTORY_KEY.format(uid=user_id, res=resource)
        try:
            history = await redis.lrange(key, 0, -1)
            bets = [int(v) for v in history]
            bets.append(amount)

            def is_triple(a: int, b: int) -> bool:
                if a == 0:
                    return False
                ratio = b / a
                return CASINO_X3_RATIO_MIN <= ratio <= CASINO_X3_RATIO_MAX

            if len(bets) >= 3:
                if is_triple(bets[-3], bets[-2]) and is_triple(bets[-2], bets[-1]):
                    return True
        except Exception as e:
            logger.warning(f"casino x3 detect error: {e}")
        return False

    async def _record_bet(self, user_id: int, resource: str, amount: int) -> None:
        """Записать ставку в историю (Redis список, 3 последних)."""
        redis = self._redis()
        key = _HISTORY_KEY.format(uid=user_id, res=resource)
        try:
            await redis.rpush(key, str(amount))
            await redis.ltrim(key, -3, -1)
            await redis.expire(key, _HISTORY_TTL)
        except Exception as e:
            logger.warning(f"casino record_bet error: {e}")

    async def reset_history(self, user_id: int, resource: str) -> None:
        """Сбросить историю ставок (после сигнала о смене ставки)."""
        redis = self._redis()
        key = _HISTORY_KEY.format(uid=user_id, res=resource)
        try:
            await redis.delete(key)
        except Exception:
            pass

    # ── Основная логика ставки ────────────────────────────────────────────────

    async def place_bet(
        self, session: AsyncSession, user: User, resource: str, amount: int
    ) -> dict:
        """
        Сделать ставку.
        Возвращает dict:
          ok: bool, win: bool, amount: int, payout: int,
          msg: str, x3_warn: bool
        """
        if resource not in CASINO_RESOURCES:
            return {"ok": False, "msg": "❌ Нельзя ставить этот ресурс."}

        balance = self.get_balance(user, resource)
        if amount <= 0:
            return {"ok": False, "msg": "❌ Ставка должна быть больше нуля."}
        if amount > balance:
            return {"ok": False, "msg": f"❌ Недостаточно {CASINO_RESOURCES[resource]}."}

        # Детектор x3
        x3 = await self._detect_x3(user.id, resource, amount)
        if x3:
            return {
                "ok": False,
                "x3_warn": True,
                "msg": (
                    "🎰 <b>Казино просит вас остановиться!</b>\n\n"
                    "Мы заметили, что вы каждый раз ставите в 3 раза больше.\n"
                    "Пожалуйста, измените размер ставки.\n\n"
                    "<i>Казино оставляет за собой право отклонить ставку.</i>"
                ),
            }

        # Записываем ставку
        await self._record_bet(user.id, resource, amount)

        # Результат
        win = random.randint(1, 100) <= WIN_CHANCE
        if win:
            payout = int(amount * WIN_MULTIPLIER)
            self.set_balance(user, resource, balance - amount + payout)
        else:
            payout = 0
            self.set_balance(user, resource, balance - amount)

        await session.flush()
        return {
            "ok": True,
            "win": win,
            "amount": amount,
            "payout": payout,
            "resource": resource,
            "resource_label": CASINO_RESOURCES[resource],
            "x3_warn": False,
        }


casino_service = CasinoService()
