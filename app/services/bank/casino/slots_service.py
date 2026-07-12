"""Слоты: 3 символа на барабане, выплаты по таблице."""
import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User

from app.constants.bank import SLOTS_SYMBOLS, SLOTS_SYMBOL_EMOJI, SLOTS_WEIGHTS, SLOTS_MULTIPLIERS
from app.services.bank.casino.common import (
    CASINO_RESOURCES, get_balance, set_balance,
    detect_x3, record_bet, add_weekly_casino_profit, X3_WARN_MSG,
)

_WEIGHTS = [SLOTS_WEIGHTS[s] for s in SLOTS_SYMBOLS]


class SlotsService:

    def spin(self) -> list[str]:
        return random.choices(SLOTS_SYMBOLS, weights=_WEIGHTS, k=3)

    def render_reel(self, reel: list[str]) -> str:
        return " | ".join(SLOTS_SYMBOL_EMOJI[s] for s in reel)

    async def play(
        self, session: AsyncSession, user: User, resource: str, amount: int
    ) -> dict:
        if resource not in CASINO_RESOURCES:
            return {"ok": False, "msg": "❌ Нельзя ставить этот ресурс."}

        balance = get_balance(user, resource)
        if amount <= 0:
            return {"ok": False, "msg": "❌ Ставка должна быть больше нуля."}
        if amount > balance:
            return {"ok": False, "msg": f"❌ Недостаточно {CASINO_RESOURCES[resource]}."}

        if await detect_x3("slots", user.id, resource, amount):
            return {"ok": False, "x3_warn": True, "msg": X3_WARN_MSG}

        await record_bet("slots", user.id, resource, amount)

        reel = self.spin()
        counts: dict[str, int] = {}
        for s in reel:
            counts[s] = counts.get(s, 0) + 1

        if 3 in counts.values():
            symbol = next(s for s, c in counts.items() if c == 3)
            multiplier = SLOTS_MULTIPLIERS[symbol]
            outcome = "triple"
        elif 2 in counts.values():
            multiplier = 1.0
            outcome = "pair"
        else:
            multiplier = 0
            outcome = "loss"

        payout = int(amount * multiplier)
        set_balance(user, resource, balance - amount + payout)
        add_weekly_casino_profit(user, resource, payout - amount)

        await session.flush()
        return {
            "ok": True,
            "reel": reel,
            "outcome": outcome,
            "amount": amount,
            "payout": payout,
            "resource": resource,
            "resource_label": CASINO_RESOURCES[resource],
            "x3_warn": False,
        }


slots_service = SlotsService()
