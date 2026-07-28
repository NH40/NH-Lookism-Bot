"""PvP-покер: жизненный цикл стола Texas Hold'em — много раздач подряд, пока
за столом остаётся ≥2 игроков со стеком (БД-логика)."""
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.poker import PokerTable, PokerPlayer
from app.constants.poker import (
    POKER_MIN_PLAYERS, POKER_MAX_PLAYERS, POKER_BUY_IN_MIN, POKER_BUY_IN_MAX,
    POKER_BIG_BLIND_RATIO, POKER_SMALL_BLIND_RATIO, POKER_RAKE_PERCENT,
    POKER_ACTION_TIMEOUT_SECONDS,
)
from app.services.bank.casino.poker_engine import new_shuffled_deck, resolve_showdown
from app.services.bank.casino.common import add_weekly_casino_profit
from app.utils.formatters import fmt_num

STREET_ORDER = ["preflop", "flop", "turn", "river"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PokerService:

    # ── Создание / вход ──────────────────────────────────────────────────────

    async def create_table(
        self, session: AsyncSession, user: User, buy_in: int, max_players: int, wait_seconds: int
    ) -> dict:
        if not (POKER_BUY_IN_MIN <= buy_in <= POKER_BUY_IN_MAX):
            return {"ok": False, "msg": f"❌ Сумма входа: от {fmt_num(POKER_BUY_IN_MIN)} до {fmt_num(POKER_BUY_IN_MAX)} NHCoin."}
        if not (POKER_MIN_PLAYERS <= max_players <= POKER_MAX_PLAYERS):
            return {"ok": False, "msg": "❌ Некорректное количество игроков."}
        if buy_in > (user.nh_coins or 0):
            return {"ok": False, "msg": "❌ Недостаточно NHCoin."}

        big_blind = max(2, buy_in // POKER_BIG_BLIND_RATIO)
        small_blind = max(1, buy_in // POKER_SMALL_BLIND_RATIO)

        user.nh_coins -= buy_in
        now = _now()
        table = PokerTable(
            creator_id=user.id,
            buy_in=buy_in, small_blind=small_blind, big_blind=big_blind,
            max_players=max_players, status="waiting",
            starts_at=now + timedelta(seconds=wait_seconds),
            created_at=now,
        )
        session.add(table)
        await session.flush()

        player = PokerPlayer(table_id=table.id, user_id=user.id, seat_index=0, stack=buy_in)
        session.add(player)
        await session.flush()

        return {"ok": True, "table": table}

    async def join_table(self, session: AsyncSession, table_id: int, user: User) -> dict:
        table = await session.get(PokerTable, table_id)
        if not table or table.status != "waiting":
            return {"ok": False, "msg": "❌ Стол недоступен."}

        players = await self._get_players(session, table_id)
        if len(players) >= table.max_players:
            return {"ok": False, "msg": "❌ Стол уже заполнен."}
        if any(p.user_id == user.id for p in players):
            return {"ok": False, "msg": "❌ Вы уже за этим столом."}
        if table.buy_in > (user.nh_coins or 0):
            return {"ok": False, "msg": "❌ Недостаточно NHCoin."}

        user.nh_coins -= table.buy_in
        seat = len(players)
        player = PokerPlayer(table_id=table.id, user_id=user.id, seat_index=seat, stack=table.buy_in)
        session.add(player)
        await session.flush()
        players.append(player)

        result: dict = {"ok": True, "table": table, "players": players, "started": False}
        if len(players) >= table.max_players:
            start_result = await self.start_hand(session, table, players)
            result["started"] = True
            result["start_result"] = start_result
        return result

    async def creator_cancel(self, session: AsyncSession, table_id: int, user_id: int) -> dict:
        table = await session.get(PokerTable, table_id)
        if not table or table.status != "waiting":
            return {"ok": False, "msg": "❌ Стол недоступен."}
        if table.creator_id != user_id:
            return {"ok": False, "msg": "❌ Только создатель может отменить стол."}
        players = await self._get_players(session, table.id)
        result = await self._cancel_table(session, table, players)
        result["ok"] = True
        return result

    async def list_open_tables(self, session: AsyncSession, limit: int = 10) -> list[PokerTable]:
        result = await session.execute(
            select(PokerTable).where(PokerTable.status == "waiting")
            .order_by(PokerTable.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_table(self, session: AsyncSession, table_id: int) -> PokerTable | None:
        return await session.get(PokerTable, table_id)

    async def get_players(self, session: AsyncSession, table_id: int) -> list[PokerPlayer]:
        return await self._get_players(session, table_id)

    async def _get_players(self, session: AsyncSession, table_id: int) -> list[PokerPlayer]:
        result = await session.execute(
            select(PokerPlayer).where(PokerPlayer.table_id == table_id).order_by(PokerPlayer.seat_index)
        )
        return list(result.scalars().all())

    # ── Раздача ───────────────────────────────────────────────────────────────

    def _post_bet(self, table: PokerTable, player: PokerPlayer, amount: int) -> None:
        player.stack -= amount
        player.current_round_bet += amount
        player.total_bet += amount
        table.pot += amount
        if player.stack == 0:
            player.status = "all_in"

    async def start_hand(self, session: AsyncSession, table: PokerTable, players: list[PokerPlayer]) -> dict:
        players = sorted(players, key=lambda p: p.seat_index)
        n = len(players)
        seats = {p.seat_index: p for p in players}

        for p in players:
            p.status = "active"
            p.current_round_bet = 0
            p.total_bet = 0
            p.has_acted = False
            p.leaving = False

        deck = new_shuffled_deck()
        for i, p in enumerate(players):
            p.hole_cards = json.dumps(deck[2 * i: 2 * i + 2])
        community = deck[2 * n: 2 * n + 5]

        table.community_cards = json.dumps(community)
        table.status = "active"
        table.current_round = "preflop"
        table.pot = 0

        # Блайнды и первый ход считаются от кнопки дилера (вращается каждую
        # раздачу в _start_new_hand_or_finish), а не от фиксированных мест —
        # иначе за многораздачным столом одни и те же места всегда были бы
        # слепыми, независимо от того, сколько раздач уже сыграно.
        dealer_seat = table.dealer_seat % n
        if n == 2:
            sb_seat, bb_seat, first_to_act = dealer_seat, (dealer_seat + 1) % n, dealer_seat
        else:
            sb_seat = (dealer_seat + 1) % n
            bb_seat = (dealer_seat + 2) % n
            first_to_act = (bb_seat + 1) % n

        sb_player, bb_player = seats[sb_seat], seats[bb_seat]
        self._post_bet(table, sb_player, min(table.small_blind, sb_player.stack))
        self._post_bet(table, bb_player, min(table.big_blind, bb_player.stack))

        table.current_bet = bb_player.current_round_bet
        table.last_raise_amount = table.big_blind
        table.current_seat = first_to_act
        table.action_deadline = _now() + timedelta(seconds=POKER_ACTION_TIMEOUT_SECONDS)

        await session.flush()
        return {"event": "hand_started", "table": table, "players": players}

    def _do_action(self, table: PokerTable, players: list[PokerPlayer], actor: PokerPlayer, action: str, amount: int | None = None) -> str | None:
        to_call = table.current_bet - actor.current_round_bet

        if action == "fold":
            actor.status = "folded"
            actor.has_acted = True
            return None

        if action == "check":
            if to_call > 0:
                return "❌ Нельзя чекнуть — есть ставка для колла."
            actor.has_acted = True
            return None

        if action == "call":
            call_amt = min(to_call, actor.stack)
            if call_amt <= 0:
                actor.has_acted = True
                return None
            self._post_bet(table, actor, call_amt)
            actor.has_acted = True
            return None

        if action == "raise":
            max_total = actor.current_round_bet + actor.stack
            if amount is None or amount <= table.current_bet:
                return "❌ Некорректная сумма рейза."
            min_total = min(table.current_bet + max(table.last_raise_amount, table.big_blind), max_total)
            if amount < min_total:
                return f"❌ Минимальный рейз — до {fmt_num(min_total)}."
            amount = min(amount, max_total)

            raise_size = amount - table.current_bet
            add_amt = amount - actor.current_round_bet
            self._post_bet(table, actor, add_amt)
            table.last_raise_amount = max(raise_size, table.last_raise_amount)
            table.current_bet = actor.current_round_bet
            actor.has_acted = True
            for p in players:
                if p is not actor and p.status == "active":
                    p.has_acted = False
            return None

        return "❌ Неизвестное действие."

    async def apply_action(self, session: AsyncSession, table: PokerTable, user_id: int, action: str, amount: int | None = None) -> dict:
        if table.status != "active":
            return {"ok": False, "msg": "❌ Раздача уже завершена."}

        players = await self._get_players(session, table.id)
        actor = next((p for p in players if p.user_id == user_id), None)
        if not actor:
            return {"ok": False, "msg": "❌ Вы не за этим столом."}
        if actor.seat_index != table.current_seat:
            return {"ok": False, "msg": "❌ Сейчас не ваш ход."}
        if actor.status != "active":
            return {"ok": False, "msg": "❌ Вы не можете сейчас действовать."}

        err = self._do_action(table, players, actor, action, amount)
        if err:
            return {"ok": False, "msg": err}

        await session.flush()
        result = await self._advance(session, table, players)
        result["ok"] = True
        result["actor_user_id"] = user_id
        result["action"] = action
        return result

    def _next_seat(self, players: list[PokerPlayer], from_seat: int) -> int:
        n = len(players)
        seats = {p.seat_index: p for p in players}
        seat = from_seat
        for _ in range(n):
            seat = (seat + 1) % n
            p = seats.get(seat)
            if p and p.status == "active":
                return seat
        return from_seat

    async def _advance(self, session: AsyncSession, table: PokerTable, players: list[PokerPlayer]) -> dict:
        active = [p for p in players if p.status == "active"]
        non_folded = [p for p in players if p.status != "folded"]

        if len(non_folded) <= 1:
            return await self._finish_hand(session, table, players, reason="fold_win")

        round_closed = all(p.current_round_bet == table.current_bet and p.has_acted for p in active)

        if not round_closed:
            table.current_seat = self._next_seat(players, table.current_seat)
            table.action_deadline = _now() + timedelta(seconds=POKER_ACTION_TIMEOUT_SECONDS)
            await session.flush()
            return {"event": "action_taken", "table": table, "players": players}

        if len(active) <= 1:
            return await self._run_out_and_showdown(session, table, players)

        return await self._next_street(session, table, players)

    async def _next_street(self, session: AsyncSession, table: PokerTable, players: list[PokerPlayer]) -> dict:
        idx = STREET_ORDER.index(table.current_round)
        if idx == len(STREET_ORDER) - 1:
            return await self._showdown(session, table, players)

        table.current_round = STREET_ORDER[idx + 1]
        table.current_bet = 0
        table.last_raise_amount = table.big_blind
        for p in players:
            p.current_round_bet = 0
            if p.status == "active":
                p.has_acted = False

        table.current_seat = self._first_seat_postflop(players, table.dealer_seat)
        table.action_deadline = _now() + timedelta(seconds=POKER_ACTION_TIMEOUT_SECONDS)
        await session.flush()
        return {"event": "street", "table": table, "players": players}

    def _first_seat_postflop(self, players: list[PokerPlayer], dealer_seat: int) -> int:
        n = len(players)
        seats = {p.seat_index: p for p in players}
        seat = dealer_seat
        for _ in range(n):
            seat = (seat + 1) % n
            p = seats.get(seat)
            if p and p.status == "active":
                return seat
        return dealer_seat

    async def _run_out_and_showdown(self, session: AsyncSession, table: PokerTable, players: list[PokerPlayer]) -> dict:
        idx = STREET_ORDER.index(table.current_round)
        while idx < len(STREET_ORDER) - 1:
            idx += 1
            table.current_round = STREET_ORDER[idx]
        return await self._showdown(session, table, players)

    async def _showdown(self, session: AsyncSession, table: PokerTable, players: list[PokerPlayer]) -> dict:
        table.current_round = "showdown"
        community = json.loads(table.community_cards)
        eval_players = [
            {
                "user_id": p.user_id,
                "hole_cards": json.loads(p.hole_cards),
                "total_bet": p.total_bet,
                "folded": p.status == "folded",
            }
            for p in players
        ]
        showdown_result = resolve_showdown(eval_players, community, POKER_RAKE_PERCENT)
        return await self._finish_hand(session, table, players, reason="showdown", showdown_result=showdown_result)

    async def _finish_hand(
        self, session: AsyncSession, table: PokerTable, players: list[PokerPlayer],
        reason: str, showdown_result: dict | None = None,
    ) -> dict:
        hands: dict[int, tuple] = {}

        if reason == "fold_win":
            winner = next(p for p in players if p.status != "folded")
            rake = int(table.pot * POKER_RAKE_PERCENT)
            payouts = {p.user_id: 0 for p in players}
            payouts[winner.user_id] = table.pot - rake
        else:
            payouts = showdown_result["payouts"]
            hands = showdown_result["hands"]
            rake = showdown_result["rake_taken"]

        table.rake_taken = rake
        table.current_seat = -1
        table.action_deadline = None

        # Выигрыш остаётся фишками на столе (в стеке) — не выводится на баланс
        # сразу. Игрок продолжает играть следующие раздачи тем же стеком, пока
        # не проиграется в ноль или сам не встанет из-за стола (see
        # _start_new_hand_or_finish). net_change — результат ИМЕННО этой
        # раздачи (выигрыш минус то, что поставил в этом кругу), не всей сессии
        # за столом — иначе цифра вводила бы в заблуждение на 2+ раздаче.
        net_changes: dict[int, int] = {}
        for p in players:
            payout = payouts.get(p.user_id, 0)
            p.stack += payout
            net_changes[p.user_id] = payout - p.total_bet

        # Снимок этой раздачи ДО continuation: если стол продолжает играть,
        # _start_new_hand_or_finish() тут же вызовет start_hand() на ТЕХ ЖЕ
        # ORM-объектах (identity map — свежий select их не пересоздаст) и
        # перезапишет table.pot/community_cards и p.status/p.hole_cards под
        # новую раздачу. Без снимка экран результата показал бы уже новые,
        # ещё не сыгранные карты вместо только что закончившейся раздачи.
        finished_pot = table.pot
        finished_community = table.community_cards
        finished_seat_order = [p.user_id for p in sorted(players, key=lambda x: x.seat_index)]
        finished_snapshot = {p.user_id: {"status": p.status, "hole_cards": p.hole_cards} for p in players}

        await session.flush()

        continuation = await self._start_new_hand_or_finish(session, table, players)

        return {
            "event": "hand_finished", "reason": reason,
            "table": table, "players": players,
            "hands": hands, "net_changes": net_changes,
            "pot": finished_pot,
            "community_cards": finished_community,
            "seat_order": finished_seat_order,
            "snapshot": finished_snapshot,
            "continuation": continuation,
        }

    async def _start_new_hand_or_finish(
        self, session: AsyncSession, table: PokerTable, players: list[PokerPlayer]
    ) -> dict:
        """После раздачи: выводит проигравшихся в ноль и тех, кто нажал "уйти",
        затем либо раздаёт следующую раздачу оставшимся, либо закрывает стол,
        если играть больше не с кем."""
        stay = [p for p in players if p.stack > 0 and not p.leaving]
        leave = [p for p in players if p not in stay]

        if leave:
            await self._cash_out(session, leave, table.buy_in)

        if len(stay) < POKER_MIN_PLAYERS:
            await self._cash_out(session, stay, table.buy_in)
            table.status = "finished"
            table.finished_at = _now()
            await session.flush()
            return {"event": "table_closed", "table": table, "players": []}

        stay_sorted = sorted(stay, key=lambda p: p.seat_index)
        for i, p in enumerate(stay_sorted):
            p.seat_index = i
        await session.flush()

        table.dealer_seat = (table.dealer_seat + 1) % len(stay_sorted)
        start_result = await self.start_hand(session, table, stay_sorted)
        return {"event": "next_hand", "table": table, "players": stay_sorted, **start_result}

    async def _cash_out(self, session: AsyncSession, players: list[PokerPlayer], buy_in: int) -> None:
        """Выводит стек игроков на баланс и убирает их со стола.
        buy_in — сколько игрок изначально заплатил за место (рёбаев нет),
        используется только для еженедельной статистики прибыли казино."""
        if not players:
            return
        user_ids = [p.user_id for p in players]
        users_result = await session.execute(select(User).where(User.id.in_(user_ids)))
        users_by_id = {u.id: u for u in users_result.scalars().all()}
        for p in players:
            u = users_by_id.get(p.user_id)
            if u:
                if p.stack > 0:
                    u.nh_coins = (u.nh_coins or 0) + p.stack
                add_weekly_casino_profit(u, "nh_coins", p.stack - buy_in)
            await session.delete(p)
        await session.flush()

    async def request_leave(self, session: AsyncSession, table_id: int, user_id: int) -> dict:
        """Игрок нажал "Уйти со стола". Если раздача ещё не идёт (стол
        активен, но между раздачами быть не может — стол либо waiting, либо
        active с раздачей в процессе) — помечаем на выход после текущей
        раздачи; сама раздача (и остальные игроки) продолжается как обычно."""
        table = await session.get(PokerTable, table_id)
        if not table:
            return {"ok": False, "msg": "❌ Стол не найден."}
        players = await self._get_players(session, table_id)
        actor = next((p for p in players if p.user_id == user_id), None)
        if not actor:
            return {"ok": False, "msg": "❌ Вы не за этим столом."}

        if table.status == "waiting":
            await self._cash_out(session, [actor], table.buy_in)
            remaining = [p for p in players if p.id != actor.id]
            if not remaining:
                table.status = "cancelled"
                table.finished_at = _now()
                await session.flush()
            return {"ok": True, "msg": "🚪 Вы вышли из-за стола, вход возвращён.", "left_now": True}

        if table.status != "active":
            return {"ok": False, "msg": "❌ Раздача уже завершена."}

        actor.leaving = True
        await session.flush()
        return {"ok": True, "msg": "🚪 Вы встанете из-за стола после текущей раздачи.", "left_now": False}

    async def _cancel_table(self, session: AsyncSession, table: PokerTable, players: list[PokerPlayer]) -> dict:
        user_ids = [p.user_id for p in players]
        users_result = await session.execute(select(User).where(User.id.in_(user_ids)))
        users_by_id = {u.id: u for u in users_result.scalars().all()}
        for p in players:
            u = users_by_id[p.user_id]
            u.nh_coins = (u.nh_coins or 0) + p.stack

        table.status = "cancelled"
        table.finished_at = _now()
        await session.flush()
        return {"event": "table_cancelled", "table": table, "players": players}

    # ── Планировщик ───────────────────────────────────────────────────────────

    async def _auto_act(self, session: AsyncSession, table: PokerTable, players: list[PokerPlayer]) -> dict:
        seats = {p.seat_index: p for p in players}
        actor = seats.get(table.current_seat)
        if not actor or actor.status != "active":
            table.action_deadline = None
            return await self._advance(session, table, players)

        to_call = table.current_bet - actor.current_round_bet
        action = "check" if to_call <= 0 else "fold"
        self._do_action(table, players, actor, action)
        await session.flush()

        result = await self._advance(session, table, players)
        result["auto"] = True
        result["actor_user_id"] = actor.user_id
        result["action"] = action
        return result

    async def tick(self, session: AsyncSession) -> list[dict]:
        events: list[dict] = []
        now = _now()

        waiting = await session.execute(
            select(PokerTable).where(PokerTable.status == "waiting", PokerTable.starts_at <= now)
        )
        for table in waiting.scalars().all():
            players = await self._get_players(session, table.id)
            if len(players) >= POKER_MIN_PLAYERS:
                events.append(await self.start_hand(session, table, players))
            else:
                events.append(await self._cancel_table(session, table, players))

        active = await session.execute(
            select(PokerTable).where(
                PokerTable.status == "active",
                PokerTable.action_deadline.is_not(None),
                PokerTable.action_deadline <= now,
            )
        )
        for table in active.scalars().all():
            players = await self._get_players(session, table.id)
            events.append(await self._auto_act(session, table, players))

        return events


poker_service = PokerService()
