"""Крафт тикетов за пыль."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.constants.cards import TICKET_CRAFT_COST


class CraftService:
    """Крафт тикетов из пыли."""

    async def craft_ticket(self, session: AsyncSession, user: User) -> dict:
        """Скрафтить 1 тикет за TICKET_CRAFT_COST пыли."""
        dust = getattr(user, "card_dust", 0)
        if dust < TICKET_CRAFT_COST:
            return {
                "ok": False,
                "reason": f"Нужно {TICKET_CRAFT_COST} 💎 пыли (у тебя {dust})"
            }
        if user.tickets >= user.max_tickets:
            return {
                "ok": False,
                "reason": f"Хранилище тикетов полно ({user.tickets}/{user.max_tickets})"
            }
        user.card_dust = dust - TICKET_CRAFT_COST
        user.tickets = min(user.max_tickets, user.tickets + 1)
        await session.flush()
        return {"ok": True, "dust_left": user.card_dust, "tickets": user.tickets}

    async def craft_ticket_bulk(self, session: AsyncSession, user: User, count: int) -> dict:
        """Скрафтить несколько тикетов сразу."""
        dust = getattr(user, "card_dust", 0)
        space = user.max_tickets - user.tickets
        can_craft = min(count, space, dust // TICKET_CRAFT_COST)

        if can_craft <= 0:
            if space <= 0:
                return {"ok": False, "reason": f"Хранилище полно ({user.tickets}/{user.max_tickets})"}
            return {"ok": False, "reason": f"Нужно {TICKET_CRAFT_COST} 💎 за тикет (у тебя {dust})"}

        total_cost = can_craft * TICKET_CRAFT_COST
        user.card_dust = dust - total_cost
        user.tickets = user.tickets + can_craft
        await session.flush()
        return {"ok": True, "crafted": can_craft, "dust_left": user.card_dust, "tickets": user.tickets}


craft_service = CraftService()
