"""Блэкджек против дилера-бота. Состояние раздачи хранится в FSM (Redis)."""
import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User

from app.constants.bank import (
    BLACKJACK_DEALER_STAND, BLACKJACK_WIN_MULTIPLIER, BLACKJACK_NATURAL_MULTIPLIER,
)
from app.services.bank.casino.common import (
    CASINO_RESOURCES, get_balance, set_balance,
    detect_x3, record_bet, add_weekly_casino_profit, X3_WARN_MSG,
)
from app.services.bank.casino.squad_service import squad_casino_service
from app.repositories.squad_repo import squad_repo

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["♠", "♥", "♦", "♣"]


def _draw_card() -> list[str]:
    """Тянет карту из «бесконечной колоды» (равные шансы каждого ранга)."""
    rank = random.choice(RANKS)
    suit = random.choice(SUITS)
    return [rank, suit]


def format_card(card: list[str]) -> str:
    return f"{card[0]}{card[1]}"


def format_hand(cards: list[list[str]]) -> str:
    return " ".join(format_card(c) for c in cards)


def hand_value(cards: list[list[str]]) -> int:
    total = 0
    aces = 0
    for rank, _ in cards:
        if rank == "A":
            total += 11
            aces += 1
        elif rank in ("J", "Q", "K"):
            total += 10
        else:
            total += int(rank)
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


def is_natural(cards: list[list[str]]) -> bool:
    return len(cards) == 2 and hand_value(cards) == 21


def _get_multiplier(resource: str) -> float:
    """Возвращает множитель выигрыша для ресурса.
    Статисты и очки пути — x1.2, остальное — x2.
    """
    if resource in ("squad", "path_points"):
        return 1.2
    return 2.0


class BlackjackService:

    async def start(
        self, session: AsyncSession, user: User, resource: str, amount: int, rank: str | None = None
    ) -> dict:
        if resource not in CASINO_RESOURCES:
            return {"ok": False, "msg": "❌ Нельзя ставить этот ресурс."}

        # Специальная обработка для статистов
        if resource == "squad":
            if not rank:
                return {"ok": False, "msg": "❌ Выберите ранг статистов."}
            
            if amount < squad_casino_service.MIN_DEPOSIT:
                return {"ok": False, "msg": f"❌ Минимальный депозит: {squad_casino_service.MIN_DEPOSIT} статистов."}
            
            if await detect_x3("blackjack", user.id, resource, amount):
                return {"ok": False, "x3_warn": True, "msg": X3_WARN_MSG}

            # Списываем статистов
            deposit_result = await squad_casino_service.deposit(session, user, rank, amount)
            if not deposit_result["ok"]:
                return {"ok": False, "msg": deposit_result["msg"]}

            await record_bet("blackjack", user.id, resource, amount)

            player_cards = [_draw_card(), _draw_card()]
            dealer_cards = [_draw_card(), _draw_card()]

            hand = {
                "resource": resource,
                "bet": amount,
                "total_stake": amount,
                "player_cards": player_cards,
                "dealer_cards": dealer_cards,
                "doubled": False,
                "rank": rank,
            }

            result = {"ok": True, "hand": hand, "finished": False}

            if is_natural(player_cards):
                if is_natural(dealer_cards):
                    # Ничья — возвращаем статистов
                    from app.data.squad import RANKS_BY_ID
                    rank_cfg = RANKS_BY_ID.get(rank)
                    if rank_cfg:
                        await squad_repo.add_count(session, user.id, rank, 0, amount, base_power=rank_cfg.base_power)
                        await squad_repo.update_user_combat_power(session, user)
                    result.update(finished=True, outcome="push_natural")
                else:
                    # Блэкджек — x1.2
                    from app.data.squad import RANKS_BY_ID
                    rank_cfg = RANKS_BY_ID.get(rank)
                    payout = int(amount * 1.2)
                    
                    if rank_cfg:
                        await squad_repo.add_count(
                            session, 
                            user.id, 
                            rank, 
                            0, 
                            payout, 
                            base_power=rank_cfg.base_power
                        )
                        await squad_repo.update_user_combat_power(session, user)
                    
                    hand["payout"] = payout
                    hand["bonus"] = 0
                    result.update(finished=True, outcome="blackjack", bonus=0)
                result["hand"] = hand
            return result

        # Обычные ресурсы
        balance = get_balance(user, resource)
        if amount <= 0:
            return {"ok": False, "msg": "❌ Ставка должна быть больше нуля."}
        if amount > balance:
            return {"ok": False, "msg": f"❌ Недостаточно {CASINO_RESOURCES[resource]}."}

        if await detect_x3("blackjack", user.id, resource, amount):
            return {"ok": False, "x3_warn": True, "msg": X3_WARN_MSG}

        await record_bet("blackjack", user.id, resource, amount)

        # Ставка списывается сразу (аналогично слотам/казино)
        set_balance(user, resource, balance - amount)
        await session.flush()

        player_cards = [_draw_card(), _draw_card()]
        dealer_cards = [_draw_card(), _draw_card()]

        hand = {
            "resource": resource,
            "bet": amount,
            "total_stake": amount,
            "player_cards": player_cards,
            "dealer_cards": dealer_cards,
            "doubled": False,
        }

        result = {"ok": True, "hand": hand, "finished": False}

        if is_natural(player_cards):
            if is_natural(dealer_cards):
                await self._settle(session, user, hand, 1.0)
                result.update(finished=True, outcome="push_natural")
            else:
                await self._settle(session, user, hand, BLACKJACK_NATURAL_MULTIPLIER)
                result.update(finished=True, outcome="blackjack")
            result["hand"] = hand
        return result

    async def hit(self, session: AsyncSession, user: User, hand: dict) -> dict:
        hand["player_cards"].append(_draw_card())
        value = hand_value(hand["player_cards"])
        if value > 21:
            await self._settle(session, user, hand, 0)
            return {"finished": True, "outcome": "bust", "hand": hand}
        return {"finished": False, "hand": hand}

    async def double(
        self, session: AsyncSession, user: User, hand: dict
    ) -> dict:
        if len(hand["player_cards"]) != 2 or hand.get("doubled"):
            return {"ok": False, "msg": "❌ Удвоить можно только первым ходом."}

        resource = hand["resource"]

        # Для статистов — отдельная логика
        if resource == "squad":
            rank = hand.get("rank")
            if not rank:
                return {"ok": False, "msg": "❌ Ранг не выбран."}
            
            extra = hand["bet"]
            # Списываем дополнительные статистов
            deposit_result = await squad_casino_service.deposit(session, user, rank, extra)
            if not deposit_result["ok"]:
                return {"ok": False, "msg": deposit_result["msg"]}
            
            hand["total_stake"] += extra
            hand["doubled"] = True
            await session.flush()

            hand["player_cards"].append(_draw_card())
            value = hand_value(hand["player_cards"])
            if value > 21:
                # Проигрыш — статисты уже списаны
                await squad_casino_service.lose(session, user, rank, hand["total_stake"])
                hand["payout"] = 0
                return {"ok": True, "finished": True, "outcome": "bust", "hand": hand}

            return await self._dealer_play_and_settle(session, user, hand)

        # Обычные ресурсы
        extra = hand["bet"]
        balance = get_balance(user, resource)
        if extra > balance:
            return {"ok": False, "msg": f"❌ Недостаточно {CASINO_RESOURCES[resource]} для удвоения."}

        set_balance(user, resource, balance - extra)
        hand["total_stake"] += extra
        hand["doubled"] = True
        await session.flush()

        hand["player_cards"].append(_draw_card())
        value = hand_value(hand["player_cards"])
        if value > 21:
            await self._settle(session, user, hand, 0)
            return {"ok": True, "finished": True, "outcome": "bust", "hand": hand}

        return await self._dealer_play_and_settle(session, user, hand)

    async def stand(self, session: AsyncSession, user: User, hand: dict) -> dict:
        return await self._dealer_play_and_settle(session, user, hand)

    async def _dealer_play_and_settle(
        self, session: AsyncSession, user: User, hand: dict
    ) -> dict:
        dealer_cards = hand["dealer_cards"]
        while hand_value(dealer_cards) < BLACKJACK_DEALER_STAND:
            dealer_cards.append(_draw_card())

        player_value = hand_value(hand["player_cards"])
        dealer_value = hand_value(dealer_cards)

        resource = hand["resource"]
        
        # Для статистов — отдельная логика
        if resource == "squad":
            rank = hand.get("rank")
            if not rank:
                return {"ok": False, "msg": "❌ Ранг не выбран."}
            
            if dealer_value > 21 or player_value > dealer_value:
                # ВЫИГРЫШ — выдаем 1.2x от ставки одной суммой
                from app.data.squad import RANKS_BY_ID
                rank_cfg = RANKS_BY_ID.get(rank)
                payout = int(hand["total_stake"] * 1.2)
                
                if rank_cfg:
                    await squad_repo.add_count(
                        session, 
                        user.id, 
                        rank, 
                        0, 
                        payout, 
                        base_power=rank_cfg.base_power
                    )
                    await squad_repo.update_user_combat_power(session, user)
                
                hand["payout"] = payout
                hand["bonus"] = 0
                return {
                    "ok": True,
                    "finished": True,
                    "outcome": "win",
                    "hand": hand,
                    "bonus": 0,
                    "returned": payout,
                }
            elif player_value == dealer_value:
                # НИЧЬЯ — возвращаем депозит
                from app.data.squad import RANKS_BY_ID
                rank_cfg = RANKS_BY_ID.get(rank)
                if rank_cfg:
                    await squad_repo.add_count(session, user.id, rank, 0, hand["total_stake"], base_power=rank_cfg.base_power)
                    await squad_repo.update_user_combat_power(session, user)
                hand["payout"] = hand["total_stake"]
                hand["bonus"] = 0
                return {"ok": True, "finished": True, "outcome": "push", "hand": hand}
            else:
                # ПРОИГРЫШ — статисты уже списаны
                await squad_casino_service.lose(session, user, rank, hand["total_stake"])
                hand["payout"] = 0
                hand["bonus"] = 0
                return {"ok": True, "finished": True, "outcome": "loss", "hand": hand}

        # Обычные ресурсы
        if dealer_value > 21 or player_value > dealer_value:
            multiplier = _get_multiplier(resource)
            outcome = "win"
        elif player_value == dealer_value:
            multiplier = 1.0
            outcome = "push"
        else:
            multiplier = 0
            outcome = "loss"

        await self._settle(session, user, hand, multiplier)
        return {"ok": True, "finished": True, "outcome": outcome, "hand": hand}

    async def _settle(
        self, session: AsyncSession, user: User, hand: dict, multiplier: float
    ) -> None:
        resource = hand["resource"]
        stake = hand["total_stake"]
        payout = int(stake * multiplier)
        balance = get_balance(user, resource)
        set_balance(user, resource, balance + payout)
        add_weekly_casino_profit(user, resource, payout - stake)
        hand["payout"] = payout
        await session.flush()


blackjack_service = BlackjackService()